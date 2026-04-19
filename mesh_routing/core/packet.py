import uuid
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Packet:
    """Represents a network packet."""
    src: int
    dst: int
    created_at: float
    packet_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    ttl: int = 10
    size: int = 512
    route: list = field(default_factory=list)
    delivered: bool = False
    delivered_at: Optional[float] = None
    dropped: bool = False
    drop_reason: Optional[str] = None
    hop_count: int = 0
    is_control: bool = False
    queued_at: Optional[float] = None
