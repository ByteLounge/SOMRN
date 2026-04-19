from typing import List, Dict, Optional
import math
from core.packet import Packet
from config import SimConfig

class Node:
    """Represents a node in the wireless mesh network."""
    def __init__(self, node_id: int, x: float, y: float, config: SimConfig):
        self.id = node_id
        self.x = x
        self.y = y
        self.config = config
        
        # Mobility variables
        self.vx = 0.0
        self.vy = 0.0
        self.target_x = x
        self.target_y = y
        self.pause_remaining = 0.0
        
        # State variables
        self.queue: List[Packet] = []
        self.queue_history: List[float] = []  # rolling window of 20 queue depth observations
        self.rssi_to: Dict[int, float] = {}   # current RSSI to each neighbor
        self.energy: float = 100.0            # Starts full, depletes per packet forwarded

    def distance_to(self, other: 'Node') -> float:
        """Calculate Euclidean distance to another node."""
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

    def update_queue_history(self) -> None:
        """Records current queue length into the history window."""
        self.queue_history.append(float(len(self.queue)))
        if len(self.queue_history) > 20:
            self.queue_history.pop(0)

    def predicted_queue_depth(self, lam: float) -> float:
        """Predict queue depth using Exponential Weighted Moving Average (EWMA)."""
        if not self.queue_history:
            return float(len(self.queue))
        
        ewma = self.queue_history[0]
        for val in self.queue_history[1:]:
            ewma = lam * val + (1 - lam) * ewma
            
        return ewma

    def energy_cost_to_forward(self) -> float:
        """Calculate energy cost to forward a single packet."""
        # Simple energy model: flat cost per transmission based on tx_power
        # In a real model this would depend on actual distance or dynamic power control
        base_cost = 0.01 
        tx_cost = (10 ** (self.config.tx_power_dbm / 10.0)) * 0.0001
        return base_cost + tx_cost
