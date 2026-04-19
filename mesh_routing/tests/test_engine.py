import pytest
import numpy as np
from simulation.engine import SimulationEngine
from config import SimConfig
from protocols.aodv import AODV
from protocols.cpqr import CPQR
from core.packet import Packet
from core.node import Node

def test_engine_initialization():
    config = SimConfig(num_nodes=10)
    engine = SimulationEngine(AODV, config)
    assert len(engine.network.nodes) == 10
    assert len(engine.flows) == config.num_flows

def test_traffic_generation():
    config = SimConfig(num_nodes=10, duration=10.0, packet_rate=10.0)
    engine = SimulationEngine(AODV, config)
    engine.run()
    
    total_sent = len(engine.metrics.sent)
    assert 400 <= total_sent <= 600

def test_packet_ttl_expiry():
    config = SimConfig(num_nodes=10)
    engine = SimulationEngine(AODV, config)
    
    pkt = Packet(src=0, dst=1, created_at=0.0)
    pkt.ttl = 0
    engine.network.nodes[0].queue.append(pkt)
    
    engine._forward_all_packets(0.1)
    
    assert len(engine.metrics.dropped) == 1
    assert engine.metrics.dropped[0][1].drop_reason == 'ttl_expired'

def test_node_energy_death():
    config = SimConfig(num_nodes=2)
    engine = SimulationEngine(CPQR, config)
    
    # Force neighbors
    engine.network.nodes[0].x, engine.network.nodes[0].y = 0, 0
    engine.network.nodes[1].x, engine.network.nodes[1].y = 50, 0
    engine.network.update_links()
    
    node = engine.network.nodes[0]
    node.energy = 0.1
    
    pkt = Packet(src=0, dst=1, created_at=0.0)
    pkt.size = 1000 # Cost = 1.0
    node.queue.append(pkt)
    
    engine._forward_all_packets(0.1)
    
    assert node.energy == 0.0

def test_energy_depletes():
    config = SimConfig(num_nodes=2)
    engine = SimulationEngine(CPQR, config)
    
    # Force neighbors
    engine.network.nodes[0].x, engine.network.nodes[0].y = 0, 0
    engine.network.nodes[1].x, engine.network.nodes[1].y = 50, 0
    engine.network.update_links()
    
    pkt = Packet(src=0, dst=1, created_at=0.0)
    pkt.size = 1000 # Cost = 1.0
    engine.network.nodes[0].queue.append(pkt)
    
    engine._forward_all_packets(0.1)
    assert engine.network.nodes[0].energy < 1000.0

def test_partition_detection_logic(caplog):
    config = SimConfig(num_nodes=10, duration=20.0)
    engine = SimulationEngine(AODV, config)
    engine.WARMUP_PERIOD = 0.0
    
    # Disconnect all nodes
    for i in range(10):
        engine.network.nodes[i].x = i * 1000 # Way out of range
    engine.network.update_links()
    
    with caplog.at_level("WARNING"):
        engine.run()
        # Should see partition warnings
        assert any("NETWORK PARTITION DETECTED" in record.message for record in caplog.records)
