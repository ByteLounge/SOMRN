import pytest
import numpy as np
from core.node import Node
from core.packet import Packet
from core.network import WirelessNetwork
from core.mobility import RandomWaypointMobility
from config import SimConfig

def test_node_distance():
    config = SimConfig()
    n1 = Node(0, 0.0, 0.0, config)
    n2 = Node(1, 3.0, 4.0, config)
    assert n1.distance_to(n2) == 5.0

def test_network_links():
    config = SimConfig(tx_range=10.0, tx_power_dbm=20.0, noise_floor_dbm=-95.0)
    net = WirelessNetwork(config)
    n1 = Node(0, 0.0, 0.0, config)
    n2 = Node(1, 5.0, 0.0, config)
    n3 = Node(2, 20.0, 0.0, config) # Out of range
    
    net.add_node(n1)
    net.add_node(n2)
    net.add_node(n3)
    net.update_links()
    
    assert net.is_connected(0, 1) == True
    assert net.is_connected(0, 2) == False
    assert net.link_quality(n1, n2) > 0.0

def test_mobility_bounds():
    config = SimConfig(area_size=100.0, min_speed=10.0, max_speed=20.0)
    net = WirelessNetwork(config)
    n1 = Node(0, 50.0, 50.0, config)
    net.add_node(n1)
    
    rng = np.random.default_rng(42)
    mob = RandomWaypointMobility(net.nodes, config, rng)
    
    for _ in range(1000):
        mob.step(0.1)
        
    assert 0.0 <= n1.x <= 100.0
    assert 0.0 <= n1.y <= 100.0

def test_packet_defaults():
    pkt = Packet(src=1, dst=2, created_at=0.0)
    assert pkt.src == 1
    assert pkt.dst == 2
    assert pkt.ttl == 10
    assert pkt.delivered == False
