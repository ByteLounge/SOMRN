from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class SimConfig:
    """Configuration parameters for the wireless mesh network simulation."""
    num_nodes: int = 30
    area_size: float = 500.0  # metres
    tx_range: float = 100.0
    tx_power_dbm: float = 20.0
    noise_floor_dbm: float = -95.0
    path_loss_exponent: float = 2.5
    max_speed: float = 5.0  # m/s
    min_speed: float = 1.0
    pause_time: float = 2.0
    packet_rate: float = 2.0  # packets/second per flow
    packet_size: int = 512  # bytes
    num_flows: int = 5
    duration: float = 300.0  # seconds
    time_step: float = 0.1  # seconds
    seed: int = 42
    alpha: float = 0.1  # Q-learning rate
    gamma: float = 0.9  # discount factor
    epsilon: float = 0.1  # exploration rate
    beta: float = 0.4  # congestion penalty weight
    lambda_ewma: float = 0.7  # queue EWMA smoothing factor
    snapshot_interval: float = 10.0
    max_queue_capacity: int = 50
    log_level: str = "INFO"
    min_explore_count: int = 5 # Minimum exploration count before using Q-values
    max_q_value: float = 1000.0 # Maximum Q-value to prevent divergence
    gamma_link: float = 0.3 # Link lifetime penalty weight
    w_e: float = 0.3 # Energy penalty weight


class ScenarioPresets:
    """Presets for different simulation scenarios."""
    
    @staticmethod
    def static_low_load() -> SimConfig:
        """A scenario with stationary nodes and low traffic."""
        return SimConfig(
            max_speed=0.0,
            min_speed=0.0,
            packet_rate=1.0,
            num_flows=2
        )

    @staticmethod
    def mobile_high_load() -> SimConfig:
        """A scenario with moving nodes and high traffic."""
        return SimConfig(
            max_speed=10.0,
            min_speed=2.0,
            packet_rate=10.0,
            num_flows=10
        )

    @staticmethod
    def stress_test() -> SimConfig:
        """A stress test scenario with many fast-moving nodes and very high load."""
        return SimConfig(
            num_nodes=50,
            max_speed=20.0,
            min_speed=5.0,
            packet_rate=20.0,
            num_flows=20,
            tx_range=80.0
        )
