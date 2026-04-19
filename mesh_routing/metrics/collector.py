from dataclasses import dataclass, field
from typing import List, Dict, Tuple
import pandas as pd
import numpy as np
from core.packet import Packet

@dataclass
class MetricsSnapshot:
    time: float
    pdr: float
    avg_delay: float
    p95_delay: float
    p99_delay: float
    throughput: float  # bytes/s
    control_overhead: int
    avg_hop_count: float
    route_breaks: int
    packets_sent: int
    packets_delivered: int
    packets_dropped: int
    energy_consumed: float

class MetricsCollector:
    """Collects and computes network performance metrics."""
    def __init__(self):
        self.sent: List[Tuple[float, Packet]] = []
        self.delivered: List[Tuple[float, Packet]] = []
        self.dropped: List[Tuple[float, Packet]] = []
        self.control_bytes: int = 0
        self.data_bytes_delivered: int = 0
        self.route_breaks: int = 0
        self.snapshots: List[MetricsSnapshot] = []
        self.energy_consumed: float = 0.0

    def on_send(self, packet: Packet, t: float):
        self.sent.append((t, packet))

    def on_deliver(self, packet: Packet, t: float):
        self.delivered.append((t, packet))
        self.data_bytes_delivered += packet.size

    def on_drop(self, packet: Packet, t: float, reason: str = None):
        packet.dropped = True
        packet.drop_reason = reason
        self.dropped.append((t, packet))

    def on_control(self, bytes_count: int):
        self.control_bytes += bytes_count

    def on_route_break(self):
        self.route_breaks += 1

    def snapshot(self, t: float, window: float = 10.0) -> MetricsSnapshot:
        """Computes metrics for the given time window."""
        recent_sent = [p for ts, p in self.sent if t - window <= ts <= t]
        recent_delivered = [p for ts, p in self.delivered if t - window <= ts <= t]
        recent_dropped = [p for ts, p in self.dropped if t - window <= ts <= t]
        
        pdr = len(recent_delivered) / len(recent_sent) if recent_sent else 0.0
        
        delays = [p.delivered_at - p.created_at for p in recent_delivered if p.delivered_at]
        avg_delay = np.mean(delays) if delays else 0.0
        p95_delay = np.percentile(delays, 95) if delays else 0.0
        p99_delay = np.percentile(delays, 99) if delays else 0.0
        
        bytes_delivered = sum(p.size for p in recent_delivered)
        throughput = bytes_delivered / window if window > 0 else 0.0
        
        hop_counts = [p.hop_count for p in recent_delivered]
        avg_hop = np.mean(hop_counts) if hop_counts else 0.0
        
        snap = MetricsSnapshot(
            time=t,
            pdr=pdr,
            avg_delay=avg_delay,
            p95_delay=p95_delay,
            p99_delay=p99_delay,
            throughput=throughput,
            control_overhead=self.control_bytes,
            avg_hop_count=avg_hop,
            route_breaks=self.route_breaks,
            packets_sent=len(self.sent),
            packets_delivered=len(self.delivered),
            packets_dropped=len(self.dropped),
            energy_consumed=self.energy_consumed
        )
        self.snapshots.append(snap)
        return snap

    def full_report(self) -> Dict:
        """Returns aggregated stats for the entire simulation."""
        pdr = len(self.delivered) / len(self.sent) if self.sent else 0.0
        delays = [p.delivered_at - p.created_at for p in [p for _, p in self.delivered] if p.delivered_at]
        
        return {
            'pdr': pdr,
            'avg_delay': np.mean(delays) if delays else 0.0,
            'throughput': self.data_bytes_delivered / self.sent[-1][0] if self.sent else 0.0,
            'control_overhead': self.control_bytes,
            'route_breaks': self.route_breaks,
            'total_sent': len(self.sent),
            'total_delivered': len(self.delivered),
            'total_dropped': len(self.dropped)
        }

    def to_dataframe(self) -> pd.DataFrame:
        """Converts snapshots to a pandas DataFrame."""
        if not self.snapshots:
            return pd.DataFrame()
        return pd.DataFrame([vars(s) for s in self.snapshots])

    def save_csv(self, path: str):
        df = self.to_dataframe()
        df.to_csv(path, index=False)
