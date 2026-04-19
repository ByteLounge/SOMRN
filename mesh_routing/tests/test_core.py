import pytest
from core.node import Node
from core.packet import Packet
from core.network import WirelessNetwork
from core.mobility import RandomWaypointMobility
from config import SimConfig

def test_node_distance():
    config = SimConfig()
    n1 = Node(1, 0, 0, config)
    n2 = Node(2, 3, 4, config)
    assert n1.distance_to(n2) == 5.0

def test_packet_creation():
    pkt = Packet(src=1, dst=2, created_at=10.0)
    assert pkt.src == 1
    assert pkt.dst == 2
    assert len(pkt.packet_id) == 8

def test_network_connectivity():
    config = SimConfig(tx_range=100.0)
    net = WirelessNetwork(config)
    n1 = Node(1, 0, 0, config)
    n2 = Node(2, 50, 0, config)
    n3 = Node(3, 140, 0, config)
    net.add_node(n1)
    net.add_node(n2)
    net.add_node(n3)
    net.update_links()
    
    assert net.is_connected(1, 2)
    assert net.is_connected(1, 3) # 1-2-3 path
    assert not net.graph.has_edge(1, 3) # Direct link should not exist

def test_mobility_bounds():
    config = SimConfig(area_size=500.0, max_speed=10.0)
    nodes = [Node(i, 250, 250, config) for i in range(5)]
    mobility = RandomWaypointMobility(nodes, config)
    
    for _ in range(100):
        mobility.step(1.0)
        for n in nodes:
            assert 0 <= n.x <= 500.0
            assert 0 <= n.y <= 500.0
