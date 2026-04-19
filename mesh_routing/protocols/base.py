from abc import ABC, abstractmethod
from typing import List, Tuple

class BaseProtocol(ABC):
    def __init__(self, network, config):
        self.network = network
        self.config = config
        self.control_bytes_sent: int = 0

    @abstractmethod
    def get_next_hop(self, node_id: int, packet) -> int:
        pass

    @abstractmethod
    def on_link_change(self, changed_edges: List[Tuple[int, int]]):
        pass

    @abstractmethod
    def on_timestep(self, t: float):
        pass

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def overhead_ratio(self, total_bytes: int) -> float:
        if total_bytes == 0:
            return 0.0
        return self.control_bytes_sent / total_bytes
