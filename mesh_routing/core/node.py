from typing import List, Dict, Optional
import math
from core.packet import Packet

class Node:
    """Represents a node in the wireless mesh network."""
    def __init__(self, id: int, x: float, y: float, config):
        self.id = id
        self.x = x
        self.y = y
        self.config = config
        
        # Mobility
        self.vx = 0.0
        self.vy = 0.0
        self.target_x = x
        self.target_y = y
        self.pause_remaining = 0.0
        
        # Queuing
        self.queue: List[Packet] = []
        self.queue_history: List[float] = []
        
        # Connectivity
        self.rssi_to: Dict[int, float] = {}
        
        # Energy
        self.energy: float = 100.0

    def distance_to(self, other: 'Node') -> float:
        """Calculates Euclidean distance to another node."""
        return math.hypot(self.x - other.x, self.y - other.y)

    def update_queue_history(self):
        """Records current queue depth."""
        self.queue_history.append(float(len(self.queue)))
        if len(self.queue_history) > 20:
            self.queue_history.pop(0)

    def predicted_queue_depth(self, lam: float) -> float:
        """Calculates EWMA of queue depth."""
        if not self.queue_history:
            return float(len(self.queue))
        ewma = self.queue_history[0]
        for q in self.queue_history[1:]:
            ewma = lam * q + (1.0 - lam) * ewma
        return ewma

    def energy_cost_to_forward(self) -> float:
        """Returns energy cost to forward a packet."""
        return 0.1  # Simplified constant cost per packet
