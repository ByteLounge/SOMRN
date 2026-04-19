from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Set
import pandas as pd
import numpy as np
from core.packet import Packet
import tempfile
import os
import shutil

@dataclass
class MetricsSnapshot:
    time: float
    pdr: float
    avg_delay: float
    p95_delay: float
    p99_delay: float
    throughput_bps: float
    control_overhead: float
    avg_hop_count: float
    route_breaks: int
    packets_sent: int
    packets_delivered: int
    packets_dropped: int
    energy_consumed: float
    avg_ral: float
    avg_link_util: float
    protocol_name: str = ""
    config_seed: int = 0
    num_nodes: int = 0
    max_speed: float = 0.0

class MetricsCollector:
    """Collects and computes network performance metrics."""
    def __init__(self, num_nodes: int):
        self.num_nodes = num_nodes
        self.sent: List[Tuple[float, Packet]] = []
        self.delivered: List[Tuple[float, Packet]] = []
        self.dropped: List[Tuple[float, Packet]] = []
        self.control_bytes: int = 0
        self.data_bytes: int = 0
        self.route_breaks: int = 0
        self.snapshots: List[MetricsSnapshot] = []
        self.energy_consumed: float = 0.0
        self.flow_start_times: Dict[int, float] = {}
        self.flow_first_delivery: Dict[int, float] = {}
        self.active_nodes_history: List[Set[int]] = []
        
        # Metadata for snapshots
        self.protocol_name = ""
        self.config_seed = 0
        self.max_speed = 0.0

    def on_send(self, packet: Packet, t: float, flow_id: int = -1):
        packet.flow_id = flow_id
        self.sent.append((t, packet))
        if flow_id != -1 and flow_id not in self.flow_start_times:
            self.flow_start_times[flow_id] = t

    def on_deliver(self, packet: Packet, t: float, flow_id: int = -1):
        packet.delivered_at = t
        self.delivered.append((t, packet))
        self.data_bytes += packet.size
        if flow_id != -1 and flow_id not in self.flow_first_delivery:
            self.flow_first_delivery[flow_id] = t

    def on_drop(self, packet: Packet, t: float, reason: str = None):
        packet.dropped = True
        packet.drop_reason = reason
        self.dropped.append((t, packet))

    def on_control(self, bytes_count: int):
        self.control_bytes += bytes_count

    def on_route_break(self):
        self.route_breaks += 1
        
    def record_active_nodes(self, active_nodes: Set[int]):
        self.active_nodes_history.append(active_nodes)

    def _compute_ral(self) -> float:
        rals = [self.flow_first_delivery[fid] - self.flow_start_times[fid] 
                for fid in self.flow_first_delivery if fid in self.flow_start_times]
        return float(np.mean(rals)) if rals else 0.0

    def _compute_link_util(self) -> float:
        if not self.active_nodes_history: return 0.0
        total_steps = len(self.active_nodes_history)
        utils = [sum(1 for step in self.active_nodes_history if nid in step) / total_steps 
                 for nid in range(self.num_nodes)]
        return float(np.mean(utils))

    def snapshot(self, t: float, window: float = 10.0) -> MetricsSnapshot:
        """BUG 4 Fix: STRICT window filter."""
        window_start = t - window

        # STRICT window filter: only packets created in this window
        sent_in_window = [
            p for ts, p in self.sent
            if window_start <= ts <= t
        ]
        delivered_in_window = [
            p for ts, p in self.delivered
            if window_start <= ts <= t
        ]

        n_sent = len(sent_in_window)
        n_delivered = len(delivered_in_window)

        pdr = n_delivered / n_sent if n_sent > 0 else 0.0

        delays = [
            p.delivered_at - p.created_at
            for p in delivered_in_window
            if p.delivered_at is not None
            and p.delivered_at > p.created_at
        ]
        avg_delay = float(np.mean(delays)) if delays else 0.0
        p95_delay = float(np.percentile(delays, 95)) if delays else 0.0
        p99_delay = float(np.percentile(delays, 99)) if delays else 0.0

        total_bytes = sum(p.size for p in delivered_in_window)
        throughput_bps = (total_bytes * 8) / window if window > 0 else 0.0

        total_bytes_all = self.data_bytes + self.control_bytes
        control_overhead = (
            self.control_bytes / total_bytes_all
            if total_bytes_all > 0 else 0.0
        )

        hops = [
            p.hop_count for p in delivered_in_window
            if p.hop_count > 0
        ]
        avg_hop_count = float(np.mean(hops)) if hops else 0.0

        dropped_in_window = [
            p for ts, p in self.dropped
            if window_start <= ts <= t
        ]

        snap = MetricsSnapshot(
            time=t,
            pdr=pdr,
            avg_delay=avg_delay,
            p95_delay=p95_delay,
            p99_delay=p99_delay,
            throughput_bps=throughput_bps,
            control_overhead=control_overhead,
            avg_hop_count=avg_hop_count,
            route_breaks=self.route_breaks,
            packets_sent=n_sent,
            packets_delivered=n_delivered,
            packets_dropped=len(dropped_in_window),
            energy_consumed=sum(
                self.net.nodes[nid].energy
                for nid in self.net.nodes
            ) if hasattr(self, 'net') else 0.0,
            avg_ral=self._compute_ral(),
            avg_link_util=self._compute_link_util(),
            protocol_name=self.protocol_name,
            config_seed=self.config_seed,
            num_nodes=self.num_nodes,
            max_speed=self.max_speed,
        )
        self.snapshots.append(snap)
        return snap

    def full_report(self) -> Dict:
        pdr = len(self.delivered) / len(self.sent) if self.sent else 0.0
        delays = [p.delivered_at - p.created_at for _, p in self.delivered if p.delivered_at]
        return {
            'pdr': pdr,
            'avg_delay': float(np.mean(delays)) if delays else 0.0,
            'throughput_bps': (self.data_bytes * 8) / self.sent[-1][0] if self.sent else 0.0,
            'control_overhead': self.control_bytes,
            'route_breaks': self.route_breaks,
            'total_sent': len(self.sent),
            'total_delivered': len(self.delivered),
            'total_dropped': len(self.dropped),
            'avg_ral': self._compute_ral()
        }

    def to_dataframe(self) -> pd.DataFrame:
        if not self.snapshots: return pd.DataFrame()
        return pd.DataFrame([vars(s) for s in self.snapshots])

    def save_csv(self, path: str):
        df = self.to_dataframe()
        fd, temp_path = tempfile.mkstemp(dir=os.path.dirname(path), prefix="tmp_metrics_", suffix=".csv")
        try:
            with os.fdopen(fd, 'w') as f: df.to_csv(f, index=False)
            shutil.move(temp_path, path)
        except Exception as e:
            if os.path.exists(temp_path): os.remove(temp_path)
            raise e
