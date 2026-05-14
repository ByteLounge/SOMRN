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

    @staticmethod
    def earthquake_response() -> tuple[SimConfig, dict]:
        cfg = SimConfig(
            num_nodes=50,
            area_size=600.0,
            max_speed=12.0,
            min_speed=3.0,
            packet_rate=4.0,
            num_flows=8,
            duration=300.0,
            tx_range=110.0,
            seed=7,
        )
        meta = {
            'name': 'Earthquake Response Zone',
            'tagline': 'Emergency responders need reliable communication '
                       'when infrastructure is destroyed.',
            'thumbnail': '🆘',
            'node_label': 'Rescue worker',
            'packet_label': 'Rescue coordination message',
            'break_label': 'Worker moved out of range',
            'congestion_label': 'Channel overloaded with distress signals',
            'recovery_label': 'Rerouted through available responder',
            'context_color': '#E74C3C',
        }
        return cfg, meta

    @staticmethod
    def campus_mesh() -> tuple[SimConfig, dict]:
        cfg = SimConfig(
            num_nodes=30,
            area_size=500.0,
            max_speed=3.0,
            min_speed=0.5,
            packet_rate=2.0,
            num_flows=5,
            duration=300.0,
            tx_range=100.0,
            seed=42,
        )
        meta = {
            'name': 'University Campus Mesh',
            'tagline': 'Campus WiFi mesh handles hundreds of students '
                       'moving between buildings.',
            'thumbnail': '🎓',
            'node_label': 'Student device',
            'packet_label': 'Data request',
            'break_label': 'Student walked out of range',
            'congestion_label': 'Too many devices in one area',
            'recovery_label': 'Rerouted through less busy path',
            'context_color': '#2980B9',
        }
        return cfg, meta

    @staticmethod
    def drone_swarm() -> tuple[SimConfig, dict]:
        cfg = SimConfig(
            num_nodes=20,
            area_size=400.0,
            max_speed=22.0,
            min_speed=8.0,
            packet_rate=5.0,
            num_flows=6,
            duration=300.0,
            tx_range=90.0,
            seed=13,
        )
        meta = {
            'name': 'Drone Swarm Coordination',
            'tagline': 'Drones coordinating a search mission need routing '
                       'that keeps up with fast movement.',
            'thumbnail': '🚁',
            'node_label': 'Drone',
            'packet_label': 'Coordination command',
            'break_label': 'Drone flew out of range',
            'congestion_label': 'Drones converging, channel saturated',
            'recovery_label': 'Rerouted through nearest drone',
            'context_color': '#27AE60',
        }
        return cfg, meta

    @staticmethod
    def get_all() -> dict:
        return {
            'earthquake': ScenarioPresets.earthquake_response(),
            'campus': ScenarioPresets.campus_mesh(),
            'drone': ScenarioPresets.drone_swarm(),
        }

