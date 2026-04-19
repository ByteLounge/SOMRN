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
    LLT_THRESHOLD = 5.0 # Seconds
    
    def __init__(self, network: WirelessNetwork, config: SimConfig):
        super().__init__(network, config)
        # Q-table: Q[node_id][dst_id][neighbor_id] = estimated cost (delay)
        self.q_table: Dict[int, Dict[int, Dict[int, float]]] = {}
        self.rng = np.random.default_rng(config.seed)
        self.in_flight: Dict[str, tuple] = {} # packet_id -> (node_id, next_hop, sent_at)
        
        for n in network.nodes:
            self.q_table[n] = {}
            
    @property
    def name(self) -> str:
        return "CPQR"

    def _get_q(self, u: int, d: int, v: int) -> float:
        if d not in self.q_table[u]:
            self.q_table[u][d] = {}
        if v not in self.q_table[u][d]:
            self.q_table[u][d][v] = 10.0 # Optimistic initial value
        return self.q_table[u][d][v]

    def get_next_hop(self, node_id: int, packet: Packet) -> int:
        dst = packet.dst
        neighbors = self.network.get_neighbors(node_id)
        if not neighbors:
            return -1
            
        # Filter neighbors by predicted link lifetime
        safe_neighbors = []
        for nb in neighbors:
            link = self.network.get_link(node_id, nb)
            if link and link.predicted_lifetime(self.config.time_step, self.config.noise_floor_dbm + 5) > self.LLT_THRESHOLD:
                safe_neighbors.append(nb)
                
        # Fallback to all neighbors if no "safe" ones exist
        viable = safe_neighbors if safe_neighbors else neighbors
        
        # Epsilon-greedy selection
        if self.rng.random() < self.config.epsilon:
            next_hop = self.rng.choice(viable)
        else:
            scores = []
            for nb in viable:
                q_val = self._get_q(node_id, dst, nb)
                # Congestion penalty
                nb_node = self.network.nodes[nb]
                cp = self.config.beta * nb_node.predicted_queue_depth(self.config.lambda_ewma)
                scores.append(q_val + cp)
            
            next_hop = viable[np.argmin(scores)]
            
        self.in_flight[packet.packet_id] = (node_id, next_hop, self.network.time)
        return next_hop

    def on_packet_delivered(self, packet: Packet):
        """Update Q-values upon successful delivery."""
        if packet.packet_id in self.in_flight:
            u, v, t_sent = self.in_flight[packet.packet_id]
            delay = self.network.time - t_sent
            dst = packet.dst
            
            old_q = self._get_q(u, dst, v)
            
            # Learn from the next hop's best Q-value to destination
            next_hop_qs = self.q_table[v].get(dst, {})
            min_q_next = min(next_hop_qs.values()) if next_hop_qs else 0.0
            
            # Q-learning update
            new_q = (1 - self.config.alpha) * old_q + self.config.alpha * (delay + self.config.gamma * min_q_next)
            self.q_table[u][dst][v] = new_q
            
            del self.in_flight[packet.packet_id]

    def on_packet_dropped(self, packet: Packet):
        """Penalize Q-values upon packet drop."""
        if packet.packet_id in self.in_flight:
            u, v, _ = self.in_flight[packet.packet_id]
            dst = packet.dst
            self.q_table[u][dst][v] = 1000.0 # High penalty
            del self.in_flight[packet.packet_id]

    def on_link_change(self, changed_edges: List):
        for u, v, status in changed_edges:
            if status == 'down':
                # Invalidate routes through this link
                for dst in self.q_table[u]:
                    if v in self.q_table[u][dst]:
                        self.q_table[u][dst][v] = 1000.0
                for dst in self.q_table[v]:
                    if u in self.q_table[v][dst]:
                        self.q_table[v][dst][u] = 1000.0

    def on_timestep(self, t: float):
        pass

    def get_qtable_stats(self) -> Dict:
        """Returns aggregate statistics about the Q-table."""
        all_vals = []
        for dst_dict in self.q_table.values():
            for nb_dict in dst_dict.values():
                all_vals.extend(nb_dict.values())
        
        if not all_vals:
            return {'mean': 0, 'max': 0, 'min': 0}
        return {
            'mean': float(np.mean(all_vals)),
            'max': float(np.max(all_vals)),
            'min': float(np.min(all_vals))
        }
