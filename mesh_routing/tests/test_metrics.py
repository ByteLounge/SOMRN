import pytest
import pandas as pd
import os
from metrics.collector import MetricsCollector
from core.packet import Packet

def test_pdr_zero_when_nothing_delivered():
    collector = MetricsCollector(2)
    collector.on_send(Packet(0, 1, 0.0), 0.0)
    snap = collector.snapshot(10.0)
    assert snap.pdr == 0.0

def test_pdr_one_when_all_delivered():
    collector = MetricsCollector(2)
    p = Packet(0, 1, 0.0)
    p.delivered_at = 1.0
    collector.on_send(p, 0.0)
    collector.on_deliver(p, 1.0)
    snap = collector.snapshot(10.0)
    assert snap.pdr == 1.0

def test_delay_excludes_dropped_packets():
    collector = MetricsCollector(2)
    p1 = Packet(0, 1, 0.0)
    p1.delivered_at = 1.0
    
    p2 = Packet(0, 1, 0.0)
    p2.dropped = True
    
    collector.on_send(p1, 0.0)
    collector.on_send(p2, 0.0)
    collector.on_deliver(p1, 1.0)
    collector.on_drop(p2, 1.0)
    
    snap = collector.snapshot(10.0)
    assert snap.avg_delay == 1.0 # Excludes p2

def test_control_overhead_ratio_between_0_and_1():
    collector = MetricsCollector(2)
    collector.on_control(100)
    p = Packet(0, 1, 0.0)
    p.size = 512
    p.delivered_at = 1.0
    collector.on_send(p, 0.0)
    collector.on_deliver(p, 1.0)
    
    snap = collector.snapshot(10.0)
    # UPDATED: instruction says ratio, so check ratio
    assert 0 <= snap.control_overhead <= 1.0
    assert snap.throughput_bps > 0

def test_snapshot_window_correct():
    collector = MetricsCollector(2)
    p1 = Packet(0, 1, 1.0)
    p1.delivered_at = 2.0
    collector.on_send(p1, 1.0)
    collector.on_deliver(p1, 2.0)
    
    p2 = Packet(0, 1, 15.0)
    p2.delivered_at = 16.0
    collector.on_send(p2, 15.0)
    collector.on_deliver(p2, 16.0)
    
    snap = collector.snapshot(20.0, window=10.0) # Window 10 to 20
    # UPDATED: STRICT window filter means only p2 is in this window
    assert snap.packets_sent == 1 
    assert snap.pdr == 1.0 # 1 sent, 1 delivered in window

def test_determinism():
    c1 = MetricsCollector(2)
    c2 = MetricsCollector(2)
    p1 = Packet(0, 1, 0.0)
    p1.delivered_at = 1.0
    
    c1.on_send(p1, 0.0)
    c1.on_deliver(p1, 1.0)
    
    c2.on_send(p1, 0.0)
    c2.on_deliver(p1, 1.0)
    
    s1 = c1.snapshot(10.0)
    s2 = c2.snapshot(10.0)
    
    assert s1.pdr == s2.pdr
    assert s1.avg_delay == s2.avg_delay

def test_to_dataframe_columns():
    collector = MetricsCollector(2)
    collector.snapshot(10.0)
    df = collector.to_dataframe()
    assert "pdr" in df.columns
    assert "avg_ral" in df.columns
    assert "avg_link_util" in df.columns

def test_save_and_reload_csv():
    collector = MetricsCollector(2)
    collector.snapshot(10.0)
    path = "tests/test_metrics.csv"
    collector.save_csv(path)
    
    df = pd.read_csv(path)
    assert len(df) == 1
    os.remove(path)
