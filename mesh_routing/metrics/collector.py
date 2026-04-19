import pandas as pd
from dataclasses import dataclass
from typing import List, Tuple, Optional

@dataclass
class MetricsSnapshot:
    time: float
    pdr: float
    avg_delay: float
    p95_delay: float
    p99_delay: float
    throughput: float
    control_overhead: float
    avg_hop_count: float
    route_breaks: int
    packets_sent: int
    packets_delivered: int
    packets_dropped: int
    energy_consumed: float

class MetricsCollector:
    def __init__(self):
        self.sent: List[Tuple[float, 'Packet']] = []
        self.delivered: List[Tuple[float, 'Packet']] = []
        self.dropped: List[Tuple[float, 'Packet', str]] = []
        
        self.control_bytes = 0
        self.data_bytes = 0
        self.route_breaks = 0
        self.energy_consumed = 0.0
        self.snapshots: List[MetricsSnapshot] = []

    def on_send(self, packet, t: float):
        self.sent.append((t, packet))
        self.data_bytes += packet.size

    def on_deliver(self, packet, t: float):
        self.delivered.append((t, packet))

    def on_drop(self, packet, t: float, reason: Optional[str] = None):
        self.dropped.append((t, packet, reason))

    def on_control(self, bytes_count: int):
        self.control_bytes += bytes_count

    def on_route_break(self):
        self.route_breaks += 1

    def snapshot(self, t: float, window: float = 10.0) -> MetricsSnapshot:
        start_t = t - window
        
        window_sent = [p for ts, p in self.sent if start_t <= ts <= t]
        window_delivered = [p for ts, p in self.delivered if start_t <= ts <= t]
        window_dropped = [p for ts, p, _ in self.dropped if start_t <= ts <= t]
        
        sent_c = len(window_sent)
        del_c = len(window_delivered)
        drop_c = len(window_dropped)
        
        pdr = del_c / sent_c if sent_c > 0 else 0.0
        
        delays = [p.delivered_at - p.created_at for ts, p in self.delivered if start_t <= ts <= t and p.delivered_at is not None]
        avg_delay = sum(delays) / len(delays) if delays else 0.0
        p95_delay = sorted(delays)[int(len(delays)*0.95)] if len(delays) >= 20 else 0.0
        p99_delay = sorted(delays)[int(len(delays)*0.99)] if len(delays) >= 100 else 0.0
        
        throughput = sum(p.size for ts, p in self.delivered if start_t <= ts <= t) / window if window > 0 else 0.0
        
        total_bytes = self.data_bytes + self.control_bytes
        overhead = self.control_bytes / total_bytes if total_bytes > 0 else 0.0
        
        hop_counts = [p.hop_count for ts, p in self.delivered if start_t <= ts <= t]
        avg_hops = sum(hop_counts) / len(hop_counts) if hop_counts else 0.0
        
        return MetricsSnapshot(
            time=t,
            pdr=pdr,
            avg_delay=avg_delay,
            p95_delay=p95_delay,
            p99_delay=p99_delay,
            throughput=throughput,
            control_overhead=overhead,
            avg_hop_count=avg_hops,
            route_breaks=self.route_breaks,
            packets_sent=sent_c,
            packets_delivered=del_c,
            packets_dropped=drop_c,
            energy_consumed=self.energy_consumed
        )

    def full_report(self) -> dict:
        total_sent = len(self.sent)
        total_delivered = len(self.delivered)
        pdr = total_delivered / total_sent if total_sent > 0 else 0.0
        
        delays = [p.delivered_at - p.created_at for ts, p in self.delivered if p.delivered_at is not None]
        avg_delay = sum(delays) / len(delays) if delays else 0.0
        
        max_t = max([ts for ts, p in self.delivered] + [ts for ts, p in self.sent] + [0.0])
        throughput = sum(p.size for ts, p in self.delivered) / max_t if max_t > 0 else 0.0
        
        total_bytes = self.data_bytes + self.control_bytes
        overhead = self.control_bytes / total_bytes if total_bytes > 0 else 0.0
        
        return {
            'PDR': pdr,
            'Avg Delay': avg_delay,
            'Throughput': throughput,
            'Control Overhead': overhead,
            'Packets Sent': total_sent,
            'Packets Delivered': total_delivered
        }

    def to_dataframe(self) -> pd.DataFrame:
        data = [{
            'time': s.time,
            'pdr': s.pdr,
            'avg_delay': s.avg_delay,
            'p95_delay': s.p95_delay,
            'p99_delay': s.p99_delay,
            'throughput': s.throughput,
            'control_overhead': s.control_overhead,
            'avg_hop_count': s.avg_hop_count,
            'route_breaks': s.route_breaks,
            'packets_sent': s.packets_sent,
            'packets_delivered': s.packets_delivered,
            'packets_dropped': s.packets_dropped,
            'energy_consumed': s.energy_consumed
        } for s in self.snapshots]
        return pd.DataFrame(data)

    def save_csv(self, path: str):
        import os
        from pathlib import Path
        Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
        df = self.to_dataframe()
        df.to_csv(path, index=False)
