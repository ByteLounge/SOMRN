import random
from typing import Dict, List, Tuple
from protocols.base import BaseProtocol
import numpy as np

class CPQR(BaseProtocol):
    def __init__(self, network, config):
        super().__init__(network, config)
        self.Q: Dict[int, Dict[int, Dict[int, float]]] = {}
        self.in_flight: Dict[str, Dict] = {} # packet_id -> {node, dst, via, sent_at}
        self.LLT_THRESHOLD = 3.0 # seconds warning before break
        
        # Initialize Q-table
        for n in network.nodes:
            self.Q[n] = {}
            for d in network.nodes:
                self.Q[n][d] = {}
                for nb in network.nodes:
                    self.Q[n][d][nb] = 10.0 # Optimistic initial value

    def get_next_hop(self, node_id: int, packet) -> int:
        dst = packet.dst
        neighbors = self.network.get_neighbors(node_id)
        
        if not neighbors:
            return -1
            
        if dst in neighbors and self._link_safe(node_id, dst):
            return dst

        viable_neighbors = [nb for nb in neighbors if self._link_safe(node_id, nb)]
        
        if not viable_neighbors:
            viable_neighbors = neighbors # Fallback
            
        if random.random() < self.config.epsilon:
            next_hop = random.choice(viable_neighbors)
        else:
            best_score = float('inf')
            next_hop = viable_neighbors[0]
            for nb in viable_neighbors:
                q_val = self.Q[node_id][dst].get(nb, 10.0)
                nb_node = self.network.nodes[nb]
                cp = self.config.beta * nb_node.predicted_queue_depth(self.config.lambda_ewma)
                score = q_val + cp
                if score < best_score:
                    best_score = score
                    next_hop = nb
                    
        self.in_flight[packet.packet_id] = {
            'node': node_id,
            'dst': dst,
            'via': next_hop,
            'sent_at': self.network.time
        }
        
        return next_hop

    def on_packet_delivered(self, packet, delivery_time: float):
        if packet.packet_id in self.in_flight:
            info = self.in_flight[packet.packet_id]
            node = info['node']
            dst = info['dst']
            via = info['via']
            delay = delivery_time - info['sent_at']
            
            old_q = self.Q[node][dst].get(via, 10.0)
            
            # min Q at next hop
            min_q_nb = 0.0
            if via != dst:
                q_vals = [self.Q[via][dst].get(n, 10.0) for n in self.network.get_neighbors(via)]
                min_q_nb = min(q_vals) if q_vals else 10.0
                
            new_q = (1 - self.config.alpha) * old_q + self.config.alpha * (delay + self.config.gamma * min_q_nb)
            self.Q[node][dst][via] = new_q
            
            del self.in_flight[packet.packet_id]

    def on_packet_dropped(self, packet):
        if packet.packet_id in self.in_flight:
            info = self.in_flight[packet.packet_id]
            node = info['node']
            dst = info['dst']
            via = info['via']
            
            self.Q[node][dst][via] = 1000.0 * 0.5 # Penalty
            del self.in_flight[packet.packet_id]

    def _link_safe(self, n1: int, n2: int) -> bool:
        link = self.network.get_link(n1, n2)
        if not link:
            return False
        return link.predicted_lifetime(self.config.time_step, self.config.noise_floor_dbm) > self.LLT_THRESHOLD

    def on_link_change(self, changed_edges: List[Tuple[int, int]]):
        broken = set(changed_edges)
        for node in self.network.nodes:
            for dst in self.network.nodes:
                for via in list(self.Q[node][dst].keys()):
                    if (node, via) in broken or (via, node) in broken:
                        self.Q[node][dst][via] = 1000.0 # INF

    def on_timestep(self, t: float):
        # RSSI updates handled by network.update_links(), Q-updates on events
        pass

    def get_qtable_stats(self) -> dict:
        stats = {}
        for n in self.network.nodes:
            vals = []
            for d in self.Q[n]:
                vals.extend(self.Q[n][d].values())
            if vals:
                stats[n] = {'mean': np.mean(vals), 'max': np.max(vals), 'min': np.min(vals)}
            else:
                stats[n] = {'mean': 10.0, 'max': 10.0, 'min': 10.0}
        return stats
