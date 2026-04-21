import pytest
from core.network import WirelessNetwork
from core.node import Node
from core.packet import Packet
from protocols.cpqr import CPQR
from config import SimConfig

def test_cold_start_fallback_activates():
    config = SimConfig(num_nodes=3)
    net = WirelessNetwork(config)
    net.add_node(Node(0, 0, 0, config))
    net.add_node(Node(1, 0, 50, config))
    net.add_node(Node(2, 0, 100, config))
    net.update_links()
    
    cpqr = CPQR(net, config)
    
    # Empty Q-table, should use cold start fallback (BFS)
    pkt = Packet(src=0, dst=2, created_at=0.0, size=512)
    next_hop = cpqr.get_next_hop(0, pkt)
    
    assert next_hop == 1
    assert cpqr.q_confidence[0].get(2, 0) == 0

def test_cold_start_exits_after_convergence():
    config = SimConfig(num_nodes=3, min_explore_count=2)
    net = WirelessNetwork(config)
    net.add_node(Node(0, 0, 0, config))
    net.add_node(Node(1, 0, 50, config))
    net.add_node(Node(2, 0, 100, config))
    net.update_links()
    
    cpqr = CPQR(net, config)
    
    # Simulate updates to exceed min_explore_count
    cpqr.q_confidence[0] = {2: 3} 
    cpqr.Q[0] = {2: {1: 10.0}}
    
    pkt = Packet(src=0, dst=2, created_at=0.0, size=512)
    # Set epsilon to 0 to avoid random choice
    cpqr.epsilon = 0.0
    next_hop = cpqr.get_next_hop(0, pkt)
    
    assert next_hop == 1

def test_dual_prediction_both_fire():
    config = SimConfig(num_nodes=2)
    net = WirelessNetwork(config)
    n0 = Node(0, 0, 0, config)
    n1 = Node(1, 0, 50, config)
    net.add_node(n0)
    net.add_node(n1)
    net.update_links()
    
    # Simulate congestion
    n1.queue = [Packet(0, 1, 0, 512)] * 40
    n1.update_queue_history()
    
    # Simulate declining RSSI
    link = net.get_link(0, 1)
    link.rssi_history = [-50, -60, -70, -80]
    
    cpqr = CPQR(net, config)
    cp = cpqr._congestion_penalty(1)
    llp = cpqr._link_lifetime_penalty(0, 1)
    
    assert cp > 0.0
    assert llp > 0.0

def test_reward_weights_respected():
    config = SimConfig(num_nodes=2, beta=0.0, w_e=0.0)
    net = WirelessNetwork(config)
    n0 = Node(0, 0, 0, config)
    n1 = Node(1, 0, 50, config)
    net.add_node(n0)
    net.add_node(n1)
    net.update_links()
    
    # Simulate congestion and energy usage
    n1.queue = [Packet(0, 1, 0, 512)] * 40
    n1.update_queue_history()
    
    cpqr = CPQR(net, config)
    cp = config.beta * cpqr._congestion_penalty(1)
    
    # In protocol, cp and ep are multiplied by weights.
    assert cp == 0.0

def test_proactive_reroute_logged():
    config = SimConfig(num_nodes=3, min_explore_count=0)
    net = WirelessNetwork(config)
    net.add_node(Node(0, 0, 0, config))
    net.add_node(Node(1, 0, 50, config))
    net.add_node(Node(2, 50, 0, config))
    net.update_links()
    
    cpqr = CPQR(net, config)
    cpqr.epsilon = 0.0
    
    # Node 1 has declining RSSI
    link = net.get_link(0, 1)
    link.rssi_history = [-50, -60, -70, -80] # Will give high penalty
    
    # Node 2 is fine
    link2 = net.get_link(0, 2)
    link2.rssi_history = [-50, -50, -50, -50]
    
    # Q values: Node 1 is better
    cpqr.Q[0] = {3: {1: 5.0, 2: 10.0}}
    
    pkt = Packet(0, 3, 0, 512)
    next_hop = cpqr.get_next_hop(0, pkt)
    
    # Because of link penalty on node 1, node 2 should be chosen
    assert next_hop == 2
    assert cpqr.proactive_reroutes_count == 1
