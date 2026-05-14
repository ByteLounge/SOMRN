# visualization/narrator.py

from dataclasses import dataclass, field
from collections import deque
import time

@dataclass
class NarrationEvent:
    message: str
    severity: str        # 'info', 'warning', 'success', 'critical'
    timestamp: float
    icon: str

class Narrator:
    """
    Converts raw simulation events into plain-English narration.
    Maintains a rolling queue of the last 6 events for display.
    Uses scenario metadata to contextualise every message.
    """

    def __init__(self, scenario_meta: dict):
        self.meta = scenario_meta
        self.events: deque[NarrationEvent] = deque(maxlen=6)
        self._delivered_total = 0
        self._dropped_total = 0
        self._break_total = 0
        self._chaos_active = False

    def on_packet_delivered(self, hop_count: int, delay: float):
        self._delivered_total += 1
        if self._delivered_total % 10 == 0:
            msg = (f"✅ {self._delivered_total} "
                   f"{self.meta['packet_label']}s delivered successfully "
                   f"across {hop_count} hops in {delay:.2f}s")
            self._add(msg, 'success', '✅')

    def on_packet_dropped(self, reason: str):
        self._dropped_total += 1
        if reason == 'ttl_expired':
            msg = (f"⚠️ A {self.meta['packet_label']} took too many "
                   f"hops and was discarded")
            self._add(msg, 'warning', '⚠️')
        elif reason == 'route_discovery_timeout':
            msg = (f"❌ Could not find a path in time — "
                   f"{self.meta['packet_label']} lost")
            self._add(msg, 'critical', '❌')

    def on_link_break(self, n1: int, n2: int):
        self._break_total += 1
        msg = (f"🔴 {self.meta['break_label']} "
               f"(connection {n1}↔{n2} lost)")
        self._add(msg, 'warning', '🔴')

    def on_route_recovered(self):
        msg = f"🟢 {self.meta['recovery_label']}"
        self._add(msg, 'success', '🟢')

    def on_congestion_predicted(self, node_id: int):
        msg = (f"🟡 {self.meta['congestion_label']} near node {node_id} "
               f"— switching route early")
        self._add(msg, 'warning', '🟡')

    def on_chaos_triggered(self):
        self._chaos_active = True
        msg = (f"🚨 NETWORK STRESS TRIGGERED — traffic doubled, "
               f"speed maxed, two nodes disabled")
        self._add(msg, 'critical', '🚨')

    def on_partition_detected(self):
        msg = "🔴 NETWORK SPLIT — fewer than half the paths are working"
        self._add(msg, 'critical', '🔴')

    def on_partition_resolved(self):
        msg = "🟢 Network recovered — paths restored"
        self._add(msg, 'success', '🟢')

    def get_feed(self) -> list[dict]:
        return [
            {
                'message': e.message,
                'severity': e.severity,
                'icon': e.icon,
                'timestamp': e.timestamp,
            }
            for e in reversed(self.events)
        ]

    def _add(self, message: str, severity: str, icon: str):
        self.events.append(NarrationEvent(
            message=message,
            severity=severity,
            timestamp=time.time(),
            icon=icon,
        ))
