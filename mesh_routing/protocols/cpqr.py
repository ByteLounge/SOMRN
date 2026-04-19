import numpy as np
from typing import Dict, List, Optional
from protocols.base import BaseProtocol
from core.packet import Packet
from core.network import WirelessNetwork
from config import SimConfig

class CPQR(BaseProtocol):
    """
    Congestion-Predictive Q-Routing (CPQR).
    A novel RL-based routing protocol that considers link lifetime and congestion.
    """
    LLT_THRESHOLD = 5.0 
    MAX_QUEUE_CAPACITY = 50
    W_E = 0.1
    EPSILON_START = 0.01 # Minimal exploration to compete with AODV
    EPSILON_DECAY = 0.0001
    EPSILON_FLOOR = 0.005
    BREAK_PENALTY: float = 100.0
    IN_FLIGHT_MAX: int = 10000
    EPISODE_STEPS: int = 100
    
    def __init__(self, network: WirelessNetwork, config: SimConfig):
        super().__init__(network, config)
        self.net = network
        self.Q: Dict[int, Dict[int, Dict[int, float]]] = {}
        self.rng = np.random.default_rng(config.seed)
        self.in_flight: Dict[str, List[dict]] = {} 
        
        self.epsilon = self.EPSILON_START
        self._step_count = 0
        
        for n in network.nodes:
            self.Q[n] = {}
            
    @property
    def name(self) -> str:
        return "CPQR"

    @property
    def q_table(self): return self.Q
    
    @property
    def INF(self): return self.BREAK_PENALTY

    def _get_q(self, node_id: int, dst: int, neighbor: int) -> float:
        """Guards against phantom neighbors (Fix C)."""
        if neighbor not in self.net.get_neighbors(node_id):
            return float('inf')
        try:
            return self.Q[node_id][dst][neighbor]
        except KeyError:
            return float('inf')

    def _congestion_penalty(self, node_id: int) -> float:
        node = self.net.nodes[node_id]
        return self.config.beta * (node.predicted_queue_depth(self.config.lambda_ewma) / self.MAX_QUEUE_CAPACITY)

    def _link_safe(self, n1: int, n2: int) -> bool:
        link = self.net.get_link(n1, n2)
        if link:
            return link.predicted_lifetime(self.config.time_step, self.config.noise_floor_dbm + 5) > self.LLT_THRESHOLD
        return False

    def get_next_hop(self, node_id: int, packet) -> int:
        """Rewritten Fix B: Epsilon-greedy with NetworkX fallback."""
        dst = packet.dst
        if node_id == dst:
            return dst

        neighbors = self.net.get_neighbors(node_id)
        if not neighbors:
            return -1

        viable = [n for n in neighbors if self._link_safe(node_id, n)]
        if not viable:
            viable = neighbors

        # Epsilon-greedy exploration
        if self.rng.random() < self.epsilon:
            chosen = int(self.rng.choice(viable))
            self._record_dispatch(packet, node_id, chosen, dst)
            return chosen

        # Exploitation: pick neighbor with lowest Q + congestion penalty
        best_hop = -1
        best_score = float('inf')
        for nb in viable:
            q_val = self._get_q(node_id, dst, nb)
            cp = self._congestion_penalty(nb)
            score = q_val + cp
            if score < best_score:
                best_score = score
                best_hop = nb

        # CRITICAL FALLBACK
        if best_score >= self.BREAK_PENALTY or best_hop == -1:
            path = self.net.shortest_path(node_id, dst)
            if len(path) >= 2:
                best_hop = path[1]
            elif viable:
                best_hop = viable[0]
            else:
                return -1

        self._record_dispatch(packet, node_id, best_hop, dst)
        return best_hop

    def _record_dispatch(self, packet, node_id: int, via: int, dst: int):
        if packet.packet_id not in self.in_flight:
            self.in_flight[packet.packet_id] = []
        
        self.in_flight[packet.packet_id].append({
            'sent_at': self.net.time,
            'node': node_id,
            'via': via,
            'dst': dst,
        })
        
        if len(self.in_flight) > self.IN_FLIGHT_MAX:
            oldest = next(iter(self.in_flight))
            del self.in_flight[oldest]

    def _add_in_flight(self, pkt_id, node, via, sent_at):
        if pkt_id not in self.in_flight: self.in_flight[pkt_id] = []
        self.in_flight[pkt_id].append({'node': node, 'via': via, 'dst': -1, 'sent_at': sent_at})

    def on_packet_delivered(self, packet: Packet, delivery_time: Optional[float] = None):
        """Update Q-values for ALL hops upon successful delivery."""
        if delivery_time is None: delivery_time = self.net.time
        if packet.packet_id in self.in_flight:
            hops = self.in_flight[packet.packet_id]
            for data in hops:
                u, v, dst, sent_at = data['node'], data['via'], data.get('dst', -1), data['sent_at']
                if dst == -1: dst = packet.dst
                
                delay = delivery_time - sent_at
                self.control_bytes_sent += 16
                energy_cost = packet.size / 1000.0
                cp = self._congestion_penalty(v)
                
                reward = delay + self.config.beta * cp + self.W_E * energy_cost
                
                if dst not in self.Q[u]: self.Q[u][dst] = {}
                old_q = self.Q[u][dst].get(v, 10.0)
                
                # Bellman update
                next_qs = [q for nb, q in self.Q.get(v, {}).get(dst, {}).items() if q < self.BREAK_PENALTY]
                min_q_next = min(next_qs) if next_qs else 0.0
                
                new_q = (1 - self.config.alpha) * old_q + self.config.alpha * (reward + self.config.gamma * min_q_next)
                self.Q[u][dst][v] = new_q
            
            del self.in_flight[packet.packet_id]

    def on_packet_dropped(self, packet: Packet):
        """Penalize Q-values for ALL hops upon packet drop."""
        if packet.packet_id in self.in_flight:
            hops = self.in_flight[packet.packet_id]
            for data in hops:
                u, v, dst = data['node'], data['via'], data.get('dst', -1)
                if dst == -1: dst = packet.dst
                if dst not in self.Q[u]:
                    self.Q[u][dst] = {}
                self.Q[u][dst][v] = self.BREAK_PENALTY
            del self.in_flight[packet.packet_id]

    def on_link_change(self, changed_edges: list):
        """Rewritten Fix C: Penalise with recoverable value. Unpack 3-tuples."""
        current_edges = set()
        for u, v in self.net.graph.edges():
            current_edges.add((min(u, v), max(u, v)))

        for edge_info in changed_edges:
            n1, n2 = edge_info[0], edge_info[1]
            edge = (min(n1, n2), max(n1, n2))
            link_broken = edge not in current_edges

            if link_broken:
                for src, broken_nb in [(n1, n2), (n2, n1)]:
                    if src in self.Q:
                        for dst in self.Q[src]:
                            if broken_nb in self.Q[src][dst]:
                                self.Q[src][dst][broken_nb] = self.BREAK_PENALTY
            else:
                for src, new_nb in [(n1, n2), (n2, n1)]:
                    if src in self.Q:
                        for dst in self.Q[src]:
                            other_vals = [v for nb, v in self.Q[src][dst].items() if nb != new_nb and v < self.BREAK_PENALTY]
                            init_val = sum(other_vals) / len(other_vals) if other_vals else 10.0
                            self.Q[src][dst][new_nb] = init_val

    def on_timestep(self, t: float):
        """Decay epsilon every 100 timesteps."""
        self._step_count = getattr(self, '_step_count', 0) + 1
        if self._step_count % 100 == 0:
            self.epsilon = max(self.EPSILON_FLOOR, self.epsilon - self.EPSILON_DECAY)

    def get_qtable_stats(self) -> Dict:
        all_vals = []
        for dst_dict in self.Q.values():
            for nb_dict in dst_dict.values():
                all_vals.extend([v for v in nb_dict.values() if v < float('inf')])
        if not all_vals: return {'mean': 0, 'max': 0, 'min': 0}
        return {
            'mean': float(np.mean(all_vals)),
            'max': float(np.max(all_vals)),
            'min': float(np.min(all_vals))
        }
