import pytest
from metrics.collector import MetricsCollector
from core.packet import Packet

def test_pdr_calculation():
    mc = MetricsCollector()
    pkt1 = Packet(1, 2, 0.0)
    pkt2 = Packet(1, 2, 0.0)
    
    mc.on_send(pkt1, 0.1)
    mc.on_send(pkt2, 0.2)
    
    pkt1.delivered_at = 0.5
    mc.on_deliver(pkt1, 0.5)
    
    snap = mc.snapshot(1.0, 10.0)
    assert snap.pdr == 0.5

def test_snapshot_window():
    mc = MetricsCollector()
    pkt1 = Packet(1, 2, 0.0)
    
    mc.on_send(pkt1, 5.0)
    mc.on_deliver(pkt1, 6.0)
    
    # Window completely past
    snap = mc.snapshot(20.0, 5.0) # start 15.0
    assert snap.packets_sent == 0
    assert snap.pdr == 0.0

def test_to_dataframe():
    mc = MetricsCollector()
    mc.snapshots.append(mc.snapshot(10.0, 10.0))
    df = mc.to_dataframe()
    assert list(df.columns) == ['time', 'pdr', 'avg_delay', 'p95_delay', 'p99_delay', 'throughput', 'control_overhead', 'avg_hop_count', 'route_breaks', 'packets_sent', 'packets_delivered', 'packets_dropped', 'energy_consumed']
