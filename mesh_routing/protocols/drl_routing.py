import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import math
from typing import Dict, List, Optional
from protocols.base import BaseProtocol
from core.packet import Packet
from core.network import WirelessNetwork
from config import SimConfig

class RoutingNet(nn.Module):
    def __init__(self, input_size=8, hidden_size=32):
        super(RoutingNet, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, 1)
        )

    def forward(self, x):
        return self.net(x)

class DRLRouting(BaseProtocol):
    """
    Deep Reinforcement Learning Routing.
    Uses a DQN-style neural network to score next-hop candidates.
    """
    BREAK_PENALTY: float = 100.0
    IN_FLIGHT_MAX: int = 5000
    
    def __init__(self, network: WirelessNetwork, config: SimConfig):
        super().__init__(network, config)
        self.net = network
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = RoutingNet().to(self.device)
        self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        self.criterion = nn.MSELoss()
        
        self.rng = np.random.default_rng(config.seed)
        self.in_flight: Dict[str, List[dict]] = {} 
        
        self.epsilon = 0.3
        self.gamma = config.gamma
        self.memory = []
        self.batch_size = 32
        
    @property
    def name(self) -> str:
        return "DRL-Routing"

    def _get_state_features(self, node_id: int, neighbor_id: int, dst_id: int) -> torch.Tensor:
        node = self.net.nodes[node_id]
        neighbor = self.net.nodes[neighbor_id]
        dst = self.net.nodes[dst_id]
        
        # Normalize features
        q_depth = len(node.queue) / 50.0
        nb_q_depth = len(neighbor.queue) / 50.0
        
        dist_to_dst = math.sqrt((node.x - dst.x)**2 + (node.y - dst.y)**2) / 500.0
        nb_dist_to_dst = math.sqrt((neighbor.x - dst.x)**2 + (neighbor.y - dst.y)**2) / 500.0
        
        link = self.net.get_link(node_id, neighbor_id)
        rssi = (link.rssi + 100) / 100.0 if link else 0.0
        
        features = [
            q_depth, 
            nb_q_depth, 
            dist_to_dst, 
            nb_dist_to_dst, 
            rssi,
            node.x / 500.0, node.y / 500.0,
            (neighbor.x - node.x) / 100.0
        ]
        return torch.tensor(features, dtype=torch.float32).to(self.device)

    def get_next_hop(self, node_id: int, packet: Packet) -> int:
        dst = packet.dst
        if node_id == dst:
            return dst

        neighbors = self.net.get_neighbors(node_id)
        if not neighbors:
            return -1

        if self.rng.random() < self.epsilon:
            chosen = int(self.rng.choice(neighbors))
            self._record_dispatch(packet, node_id, chosen, dst)
            return chosen

        # Score neighbors using the NN
        self.model.eval()
        with torch.no_grad():
            best_hop = -1
            best_score = -float('inf')
            
            for nb in neighbors:
                state = self._get_state_features(node_id, nb, dst)
                score = self.model(state).item()
                if score > best_score:
                    best_score = score
                    best_hop = nb

        if best_hop == -1:
            best_hop = neighbors[0]

        self._record_dispatch(packet, node_id, best_hop, dst)
        return best_hop

    def _record_dispatch(self, packet, node_id: int, via: int, dst: int):
        if packet.packet_id not in self.in_flight:
            self.in_flight[packet.packet_id] = []
        
        state = self._get_state_features(node_id, via, dst)
        self.in_flight[packet.packet_id].append({
            'state': state,
            'node': node_id,
            'via': via,
            'dst': dst,
            'sent_at': self.net.time
        })

    def on_packet_delivered(self, packet: Packet, delivery_time: Optional[float] = None):
        if delivery_time is None: delivery_time = self.net.time
        
        if packet.packet_id in self.in_flight:
            hops = self.in_flight[packet.packet_id]
            for i, data in enumerate(hops):
                delay = delivery_time - data['sent_at']
                reward = -delay # Negative delay as reward
                
                # Simple Q-learning target
                self.memory.append((data['state'], reward))
                
            del self.in_flight[packet.packet_id]
            
        if len(self.memory) >= self.batch_size:
            self._train()

    def on_packet_dropped(self, packet: Packet):
        if packet.packet_id in self.in_flight:
            hops = self.in_flight[packet.packet_id]
            for data in hops:
                self.memory.append((data['state'], -self.BREAK_PENALTY))
            del self.in_flight[packet.packet_id]

    def _train(self):
        self.model.train()
        batch = self.rng.choice(len(self.memory), size=min(len(self.memory), self.batch_size), replace=False)
        
        states = []
        targets = []
        for i in batch:
            state, reward = self.memory[i]
            states.append(state)
            targets.append(torch.tensor([reward], dtype=torch.float32).to(self.device))
            
        states_t = torch.stack(states)
        targets_t = torch.stack(targets)
        
        self.optimizer.zero_grad()
        outputs = self.model(states_t)
        loss = self.criterion(outputs, targets_t)
        loss.backward()
        self.optimizer.step()
        
        # Clear memory occasionally to prevent stale data
        if len(self.memory) > 1000:
            self.memory = self.memory[-500:]

    def on_link_change(self, changed_edges: list):
        pass

    def on_timestep(self, t: float):
        self.epsilon = max(0.05, self.epsilon * 0.999)
