import numpy as np
from typing import Dict, List, Optional
from protocols.base import BaseProtocol
from core.packet import Packet
from core.network import WirelessNetwork
from config import SimConfig

class PQR(BaseProtocol):
    """
    Predictive Q-Routing (PQR).
    Incorporates a recovery rate (best-case delay) to adapt faster to congestion.
    """
    BREAK_PENALTY: float = 100.0
    IN_FLIGHT_MAX: int = 10000
    
    def __init__(self, network: WirelessNetwork, config: SimConfig):
        super().__init__(network, config)
        self.net = network
        self.Q: Dict[int, Dict[int, Dict[int, float]]] = {}
        self.B: Dict[int, Dict[int, Dict[int, float]]] = {} # Best-case delay (Recovery rate)
        self.rng = np.random.default_rng(config.seed)
        self.in_flight: Dict[str, List[dict]] = {} 
        
        self.epsilon = 0.2
        self.alpha = 0.5
        self.beta = 0.1 # Weight for predictive recovery
        self.gamma = config.gamma
        
        for n in network.nodes:
            self.Q[n] = {}
            self.B[n] = {}
            
    @property
    def name(self) -> str:
        return "PQR"

    def _get_q(self, node_id: int, dst: int, neighbor: int) -> float:
        if neighbor not in self.net.get_neighbors(node_id):
            return self.BREAK_PENALTY
        try:
            return self.Q[node_id][dst][neighbor]
        except KeyError:
            return 10.0

    def _get_b(self, node_id: int, dst: int, neighbor: int) -> float:
        try:
            return self.B[node_id][dst][neighbor]
        except KeyError:
            return 2.0 # Optimistic best-case

    def get_next_hop(self, node_id: int, packet: Packet) -> int:
        dst = packet.dst
        if node_id == dst:
            return dst

        neighbors = self.net.get_neighbors(node_id)
        if not neighbors:
            return -1

        if self.rng.random() < self.epsilon:
            return int(self.rng.choice(neighbors))

        best_hop = -1
        best_score = float('inf')
        
        for nb in neighbors:
            score = self._get_q(node_id, dst, nb)
            if score < best_score:
                best_score = score
                best_hop = nb

        if best_hop == -1 or best_score >= self.BREAK_PENALTY:
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
                self.control_bytes_sent += 12
                
                if dst not in self.Q[u]: self.Q[u][dst] = {}
                if dst not in self.B[u]: self.B[u][dst] = {}
                
                old_q = self.Q[u][dst].get(v, 10.0)
                old_b = self.B[u][dst].get(v, 2.0)
                
                # Update Best-case (Recovery rate)
                new_b = min(old_b, delay)
                self.B[u][dst][v] = new_b
                
                # PQR Update rule
                # Q(u,d,v) = (1-a)Q(u,d,v) + a(delay + gamma * min Q(v,d,v'))
                # With recovery prediction: if Q increases, it's congestion.
                next_qs = [q for nb, q in self.Q.get(v, {}).get(dst, {}).items() if q < self.BREAK_PENALTY]
                min_q_next = min(next_qs) if next_qs else 0.0
                
                target = delay + self.gamma * min_q_next
                
                # PQR adjustment: speed up recovery if target < old_q
                learning_rate = self.alpha
                if target < old_q:
                    # Predicted faster recovery
                    learning_rate = self.alpha * (1 + self.beta)
                
                new_q = (1 - learning_rate) * old_q + learning_rate * target
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
        pass

    def on_timestep(self, t: float):
        pass
