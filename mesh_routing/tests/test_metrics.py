import pytest
import pandas as pd
from metrics.collector import MetricsCollector
from core.packet import Packet

def test_pdr_calculation():
    collector = MetricsCollector()
    p1 = Packet(0, 1, 0.0)
    p2 = Packet(0, 1, 0.0)
    p3 = Packet(0, 1, 0.0)
    
    collector.on_send(p1, 0.0)
    collector.on_send(p2, 0.1)
    collector.on_send(p3, 0.2)
    
    p1.delivered_at = 0.5
    collector.on_deliver(p1, 0.5)
    
    snap = collector.snapshot(1.0, window=1.0)
    assert snap.pdr == 1/3
    assert snap.packets_sent == 3
    assert snap.packets_delivered == 1

def test_dataframe_conversion():
    collector = MetricsCollector()
    collector.on_send(Packet(0, 1, 0.0), 0.0)
    collector.snapshot(10.0)
    collector.snapshot(20.0)
    
    df = collector.to_dataframe()
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert "pdr" in df.columns
