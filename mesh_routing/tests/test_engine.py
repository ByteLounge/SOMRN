import pytest
import numpy as np
from config import SimConfig
from simulation.engine import SimulationEngine
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR
from core.packet import Packet

def test_engine_completes_without_exception_aodv():
    config = SimConfig(num_nodes=10, duration=10, num_flows=2)
    engine = SimulationEngine(AODV, config)
    engine.run()

def test_engine_completes_without_exception_olsr():
    config = SimConfig(num_nodes=10, duration=10, num_flows=2)
    engine = SimulationEngine(OLSR, config)
    engine.run()

def test_engine_completes_without_exception_cpqr():
    config = SimConfig(num_nodes=10, duration=10, num_flows=2)
    engine = SimulationEngine(CPQR, config)
    engine.run()

def test_engine_determinism():
    c1 = SimConfig(num_nodes=10, duration=10, seed=42, num_flows=2)
    e1 = SimulationEngine(CPQR, c1)
    m1 = e1.run()
    s1 = m1.snapshot(10)
    
    c2 = SimConfig(num_nodes=10, duration=10, seed=42, num_flows=2)
    e2 = SimulationEngine(CPQR, c2)
    m2 = e2.run()
    s2 = m2.snapshot(10)
    
    assert s1.pdr == s2.pdr
    
def test_packet_ttl_expiry_recorded():
    config = SimConfig(num_nodes=2, duration=2)
    engine = SimulationEngine(AODV, config)
    
    # Inject a packet with TTL 0
    pkt = Packet(0, 1, 0)
    pkt.ttl = 0
    engine.network.nodes[0].queue.append(pkt)
    
    engine._forward_all_packets(0.1)
    
    assert any(p.drop_reason == "ttl_expired" for t, p in engine.metrics.dropped)

def test_energy_depletes():
    config = SimConfig(num_nodes=2, duration=20, tx_range=500.0)
    engine = SimulationEngine(CPQR, config)
    pkt = Packet(0, 1, 0, size=1000)
    engine.network.nodes[0].queue.append(pkt)
    engine._forward_all_packets(0.1)
    
    assert engine.network.nodes[0].energy < 100.0

def test_poisson_arrivals():
    config = SimConfig(num_nodes=5, duration=100, packet_rate=2.0)
    engine = SimulationEngine(AODV, config)
    engine.run()
    
    sent = [t for t, p in engine.metrics.sent]
    if len(sent) > 2:
        diffs = [sent[i] - sent[i-1] for i in range(1, len(sent))]
        mean_diff = np.mean(diffs)
        # Expected inter-arrival time across all flows is 1 / (packet_rate * num_flows) = 1/10 = 0.1
        assert 0.05 < mean_diff < 0.2
