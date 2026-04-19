import pytest
import json
from core.node import Node
from core.packet import Packet
from core.network import WirelessNetwork
from core.mobility import RandomWaypointMobility
from config import SimConfig

def test_node_distance_symmetry():
    config = SimConfig()
    n1 = Node(1, 0, 0, config)
    n2 = Node(2, 3, 4, config)
    assert n1.distance_to(n2) == n2.distance_to(n1)
    assert n1.distance_to(n2) == 5.0

def test_node_stays_in_bounds():
    config = SimConfig(area_size=500.0, max_speed=10.0)
    nodes = [Node(i, 250, 250, config) for i in range(5)]
    mobility = RandomWaypointMobility(nodes, config)
    
    for _ in range(10000):
        mobility.step(0.1)
        
    for n in nodes:
        assert 0 <= n.x <= 500.0
        assert 0 <= n.y <= 500.0

def test_queue_history_capped_at_20():
    config = SimConfig()
    n = Node(1, 0, 0, config)
    for i in range(25):
        n.queue = [Packet(0, 1, 0.0)] * i
        n.update_queue_history()
        
    assert len(n.queue_history) == 20
    assert n.queue_history[-1] == 24.0

def test_predicted_queue_depth_zero_for_empty_queue():
    config = SimConfig()
    n = Node(1, 0, 0, config)
    assert n.predicted_queue_depth(0.7) == 0.0

def test_link_quality_zero_beyond_range():
    config = SimConfig(tx_range=100.0)
    net = WirelessNetwork(config)
    n1 = Node(1, 0, 0, config)
    n2 = Node(2, 101, 0, config)
    assert net.link_quality(n1, n2) == 0.0

def test_rssi_decreases_with_distance():
    config = SimConfig()
    net = WirelessNetwork(config)
    n1 = Node(1, 0, 0, config)
    distances = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    rssi_vals = []
    for d in distances:
        n2 = Node(2, d, 0, config)
        rssi_vals.append(net.rssi(n1, n2))
        
    for i in range(len(rssi_vals) - 1):
        assert rssi_vals[i] > rssi_vals[i+1]

def test_network_update_links_correct_edge_count():
    config = SimConfig(tx_range=100.0)
    net = WirelessNetwork(config)
    # Triangle where side lengths are < 100
    net.add_node(Node(1, 0, 0, config))
    net.add_node(Node(2, 50, 0, config))
    net.add_node(Node(3, 25, 43, config)) # Equilateral-ish
    net.update_links()
    assert net.graph.number_of_edges() == 3

def test_topology_snapshot_serialisable():
    config = SimConfig()
    net = WirelessNetwork(config)
    net.add_node(Node(1, 0, 0, config))
    net.add_node(Node(2, 50, 0, config))
    net.update_links()
    snap = net.topology_snapshot()
    try:
        json.dumps(snap)
    except TypeError:
        pytest.fail("Snapshot is not JSON serializable")
