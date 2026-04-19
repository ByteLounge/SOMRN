import numpy as np
from typing import List

class Link:
    """Represents a wireless link between two nodes."""
    def __init__(self, n1_id: int, n2_id: int):
        self.n1_id = n1_id
        self.n2_id = n2_id
        self.quality: float = 1.0  # 0 to 1
        self.rssi: float = 0.0     # dBm
        self.active: bool = False
        self.last_seen: float = 0.0
        self.rssi_history: List[float] = []  # Last 15 observations

    def update(self, rssi: float, t: float) -> None:
        """Updates link state with new RSSI observation."""
        self.rssi = rssi
        self.last_seen = t
        self.active = True
        
        self.rssi_history.append(rssi)
        if len(self.rssi_history) > 15:
            self.rssi_history.pop(0)

    def predicted_lifetime(self, time_step: float, threshold: float) -> float:
        """
        Predicts how long the link will remain above the given threshold.
        Uses linear regression on rssi_history.
        Returns float('inf') if stable or increasing.
        """
        if len(self.rssi_history) < 3:
            return float('inf')  # Not enough data
            
        x = np.arange(len(self.rssi_history))
        y = np.array(self.rssi_history)
        
        try:
            # Linear regression: y = mx + c
            m, c = np.polyfit(x, y, 1)
        except np.linalg.LinAlgError:
            return float('inf')

        if m >= -0.01:
            return float('inf')  # Stable or increasing (allow small negative slope as stable)
            
        # steps_to_fail * m + current_rssi = threshold
        # steps_to_fail = (threshold - current_rssi) / m
        current_rssi = self.rssi_history[-1]
        if current_rssi <= threshold:
            return 0.0
            
        steps_to_fail = (threshold - current_rssi) / m
        if steps_to_fail < 0:
            return float('inf') # Should be handled by m >= 0 check, but safe guard
            
        return steps_to_fail * time_step
