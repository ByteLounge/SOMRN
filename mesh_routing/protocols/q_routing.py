import numpy as np
from typing import Dict, List, Optional
from protocols.base import BaseProtocol
from core.packet import Packet
from core.network import WirelessNetwork
from config import SimConfig

class QRouting(BaseProtocol):
    """
    Standard Q-Routing.
    Basic RL-based routing focusing on path delay.
    """
    BREAK_PENALTY: float = 100.0
    IN_FLIGHT_MAX: int = 10000
    
    def __init__(self, network: WirelessNetwork, config: SimConfig):
        super().__init__(network, config)
        self.net = network
        self.Q: Dict[int, Dict[int, Dict[int, float]]] = {}
        self.rng = np.random.default_rng(config.seed)
        self.in_flight: Dict[str, List[dict]] = {} 
        
        self.epsilon = 0.2
        self.alpha = 0.5
        self.gamma = config.gamma
        
        for n in network.nodes:
            self.Q[n] = {}
            
    @property
    def name(self) -> str:
        return "Q-Routing"

    def _get_q(self, node_id: int, dst: int, neighbor: int) -> float:
        if neighbor not in self.net.get_neighbors(node_id):
            return self.BREAK_PENALTY
        try:
            return self.Q[node_id][dst][neighbor]
        except KeyError:
            return 10.0 # Initial guess

    def get_next_hop(self, node_id: int, packet: Packet) -> int:
        dst = packet.dst
        if node_id == dst:
            return dst

        neighbors = self.net.get_neighbors(node_id)
        if not neighbors:
            return -1

        # Epsilon-greedy exploration
        if self.rng.random() < self.epsilon:
            return int(self.rng.choice(neighbors))

        # Exploitation: pick neighbor with lowest Q
        best_hop = -1
        best_score = float('inf')
        
        for nb in neighbors:
            score = self._get_q(node_id, dst, nb)
            if score < best_score:
                best_score = score
                best_hop = nb

        if best_hop == -1 or best_score >= self.BREAK_PENALTY:
            # Fallback to shortest path if no good Q-info
            path = self.net.shortest_path(node_id, dst)
            if len(path) >= 2:
                best_hop = path[1]
            else:
                best_hop = neighbors[0]

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

    def on_packet_delivered(self, packet: Packet, delivery_time: Optional[float] = None):
        if delivery_time is None: delivery_time = self.net.time
        
        if packet.packet_id in self.in_flight:
            hops = self.in_flight[packet.packet_id]
            for data in hops:
                u, v, dst, sent_at = data['node'], data['via'], data['dst'], data['sent_at']
                
                delay = delivery_time - sent_at
                self.control_bytes_sent += 8 # Small feedback packet
                
                if dst not in self.Q[u]: self.Q[u][dst] = {}
                old_q = self.Q[u][dst].get(v, 10.0)
                
                # Standard Q-learning update
                # Q(u,d,v) = (1-a)Q(u,d,v) + a(delay + gamma * min Q(v,d,v'))
                next_qs = [q for nb, q in self.Q.get(v, {}).get(dst, {}).items() if q < self.BREAK_PENALTY]
                min_q_next = min(next_qs) if next_qs else 0.0
                
                new_q = (1 - self.alpha) * old_q + self.alpha * (delay + self.gamma * min_q_next)
                self.Q[u][dst][v] = new_q
            
            del self.in_flight[packet.packet_id]

    def on_packet_dropped(self, packet: Packet):
        if packet.packet_id in self.in_flight:
            hops = self.in_flight[packet.packet_id]
            for data in hops:
                u, v, dst = data['node'], data['via'], data['dst']
                if dst not in self.Q[u]: self.Q[u][dst] = {}
                self.Q[u][dst][v] = self.BREAK_PENALTY
            del self.in_flight[packet.packet_id]

    def on_link_change(self, changed_edges: list):
        pass # Simple Q-Routing handles this through packet drops

    def on_timestep(self, t: float):
        pass
