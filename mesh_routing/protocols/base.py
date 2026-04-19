from abc import ABC, abstractmethod
from typing import List
from config import SimConfig
from core.network import WirelessNetwork
from core.packet import Packet

class BaseProtocol(ABC):
    """Abstract base class for routing protocols."""
    def __init__(self, network: WirelessNetwork, config: SimConfig):
        self.network = network
        self.config = config
        self.control_bytes_sent: int = 0

    @abstractmethod
    def get_next_hop(self, node_id: int, packet: Packet) -> int:
        """Determines the next hop for a packet at a given node. Returns -1 if no route."""
        pass

    @abstractmethod
    def on_link_change(self, changed_edges: List):
        """Called when network topology changes."""
        pass

    @abstractmethod
    def on_timestep(self, t: float):
        """Called at every simulation time step."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Returns the protocol name."""
        pass

    def overhead_ratio(self, total_bytes: int) -> float:
        """Calculates the control overhead ratio."""
        if total_bytes == 0:
            return 0.0
        return self.control_bytes_sent / total_bytes
