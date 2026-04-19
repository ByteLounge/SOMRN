import numpy as np
from typing import List

class Link:
    """Represents a wireless link between two nodes."""
    def __init__(self, n1_id: int, n2_id: int):
        self.n1_id = n1_id
        self.n2_id = n2_id
        self.quality: float = 1.0
        self.rssi: float = -50.0
        self.active: bool = True
        self.last_seen: float = 0.0
        self.rssi_history: List[float] = []

    def update(self, rssi: float, t: float):
        """Updates link status with new RSSI reading."""
        self.rssi = rssi
        self.last_seen = t
        self.active = True
        self.rssi_history.append(rssi)
        if len(self.rssi_history) > 15:
            self.rssi_history.pop(0)

    def predicted_lifetime(self, time_step: float, threshold: float) -> float:
        """Predicts time until link RSSI drops below threshold."""
        if len(self.rssi_history) < 2:
            return float('inf')
        
        x = np.arange(len(self.rssi_history))
        y = np.array(self.rssi_history)
        
        # Linear regression
        slope, intercept = np.polyfit(x, y, 1)
        
        if slope >= 0:
            return float('inf')  # Stable or improving
            
        steps_to_fail = (threshold - self.rssi) / slope
        if steps_to_fail < 0:
            return 0.0
            
        return steps_to_fail * time_step
