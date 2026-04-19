import pytest
from core.network import WirelessNetwork
from core.node import Node
from core.packet import Packet
from config import SimConfig
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR

# AODV Tests
def test_aodv_route_discovery_5_node_chain():
    config = SimConfig(tx_range=100.0)
    net = WirelessNetwork(config)
    for i in range(5):
        net.add_node(Node(i, i*80, 0, config))
    net.update_links()
    
    aodv = AODV(net, config)
    pkt = Packet(src=0, dst=4, created_at=0.0)
    
    next_hop = aodv.get_next_hop(0, pkt)
    assert next_hop == -1
    
    # Discovery should complete iteratively
    assert 4 in aodv.routing_tables[0]
    assert aodv.routing_tables[0][4].next_hop == 1

def test_aodv_route_invalidation_on_break():
    config = SimConfig(tx_range=100.0)
    net = WirelessNetwork(config)
    for i in range(3):
        net.add_node(Node(i, i*80, 0, config))
    net.update_links()
    aodv = AODV(net, config)
    aodv.get_next_hop(0, Packet(0, 2, 0)) # Form route
    
    # Simulate a longer route to bypass local repair (hop < 5)
    aodv.routing_tables[1][2].hop_count = 10
    
    # Break link
    aodv.on_link_change([(1, 2, 'down')])
    
    # 0 -> 2 goes via 1, so 1 breaking link to 2 should send RERR to 0
    # Our simple RERR invalidates immediately in precursors
    assert 2 not in aodv.routing_tables[0]

def test_aodv_seq_number_increment():
    config = SimConfig()
    net = WirelessNetwork(config)
    net.add_node(Node(0, 0, 0, config))
    net.add_node(Node(1, 50, 0, config))
    net.update_links()
    aodv = AODV(net, config)
    
    initial_seq = aodv.node_seq_num[0]
    aodv._discover_route(0, Packet(0, 1, 0))
    assert aodv.node_seq_num[0] == initial_seq + 1

def test_aodv_rreq_dedup():
    config = SimConfig()
    net = WirelessNetwork(config)
    net.add_node(Node(0, 0, 0, config))
    net.add_node(Node(1, 50, 0, config))
    net.update_links()
    aodv = AODV(net, config)
    
    aodv._add_seen_rreq(0, src=1, rreq_id=100)
    assert (1, 100) in aodv.seen_rreqs[0]
    
    aodv._add_seen_rreq(0, src=1, rreq_id=100)
    assert len(aodv.seen_rreqs[0]) == 1 # Still 1

# OLSR Tests
def test_olsr_mpr_covers_all_2hop():
    config = SimConfig(tx_range=100.0)
    net = WirelessNetwork(config)
    net.add_node(Node(0, 100, 100, config))
    net.add_node(Node(1, 150, 100, config))
    net.add_node(Node(2, 50, 100, config))
    net.add_node(Node(3, 100, 150, config))
    net.add_node(Node(4, 230, 100, config)) # 2 hop via 1
    net.add_node(Node(5, -30, 100, config)) # 2 hop via 2
    net.update_links()
    olsr = OLSR(net, config)
    
    # Force willingness to DEFAULT for the test so modulo logic doesn't mess it up
    for n in net.nodes:
        olsr.node_willingness[n] = olsr.WILL_DEFAULT
        
    # Simulate HELLOs from all
    for n in net.nodes:
        olsr._send_hello(n, 0)
    # Simulate HELLOs again to make links symmetric
    for n in net.nodes:
        olsr._send_hello(n, 1)
        
    olsr._select_mprs(0)
        
    assert 1 in olsr.mpr_set[0]
    assert 2 in olsr.mpr_set[0]

def test_olsr_routing_table_non_empty_after_convergence():
    config = SimConfig(tx_range=100.0)
    net = WirelessNetwork(config)
    for i in range(3): net.add_node(Node(i, i*80, 0, config))
    net.update_links()
    olsr = OLSR(net, config)
    for _ in range(50):
        olsr.on_timestep(net.time)
        net.time += 0.1
    
    assert 2 in olsr.routing_table[0]

def test_olsr_stale_topology_purged():
    config = SimConfig(tx_range=100.0)
    net = WirelessNetwork(config)
    net.add_node(Node(0, 0, 0, config))
    net.add_node(Node(1, 50, 0, config))
    net.update_links()
    olsr = OLSR(net, config)
    
    from protocols.olsr import TopologyEntry
    olsr.topology_table.append(TopologyEntry(1, 2, 1, 10.0))
    olsr.on_timestep(11.0)
    assert len(olsr.topology_table) == 0

# CPQR Tests
def test_cpqr_qvalue_decreases_after_delivery():
    config = SimConfig()
    net = WirelessNetwork(config)
    net.add_node(Node(0, 0, 0, config))
    net.add_node(Node(1, 50, 0, config))
    net.update_links()
    
    cpqr = CPQR(net, config)
    pkt = Packet(src=0, dst=1, created_at=0.0)
    
    _ = cpqr.get_next_hop(0, pkt)
    net.time = 0.5 # Small delay
    cpqr.on_packet_delivered(pkt, 0.5)
    
    assert cpqr.Q[0][1][1] < 10.0

def test_cpqr_qvalue_penalised_after_drop():
    config = SimConfig()
    net = WirelessNetwork(config)
    net.add_node(Node(0, 0, 0, config))
    net.add_node(Node(1, 50, 0, config))
    net.update_links()
    
    cpqr = CPQR(net, config)
    pkt = Packet(src=0, dst=1, created_at=0.0)
    _ = cpqr.get_next_hop(0, pkt)
    cpqr.on_packet_dropped(pkt)
    assert cpqr.Q[0][1][1] == cpqr.BREAK_PENALTY

def test_cpqr_epsilon_decays_over_time():
    config = SimConfig()
    net = WirelessNetwork(config)
    cpqr = CPQR(net, config)
    initial_eps = cpqr.epsilon
    for _ in range(cpqr.EPISODE_STEPS):
        cpqr.on_timestep(0)
    assert cpqr.epsilon < initial_eps

def test_cpqr_link_lifetime_inf_for_stable_link():
    config = SimConfig()
    net = WirelessNetwork(config)
    net.add_node(Node(0, 0, 0, config))
    net.add_node(Node(1, 50, 0, config))
    net.update_links()
    
    link = net.get_link(0, 1)
    for _ in range(10):
        link.update(-50, 0) # Flat RSSI
    assert link.predicted_lifetime(0.1, -95) == float('inf')

def test_cpqr_link_lifetime_finite_for_declining_link():
    config = SimConfig()
    net = WirelessNetwork(config)
    net.add_node(Node(0, 0, 0, config))
    net.add_node(Node(1, 50, 0, config))
    net.update_links()
    
    link = net.get_link(0, 1)
    rssi = -50
    for _ in range(10):
        link.update(rssi, 0) 
        rssi -= 5 # Declining
    assert link.predicted_lifetime(0.1, -95) < float('inf')

def test_cpqr_congestion_penalty_normalised():
    config = SimConfig()
    net = WirelessNetwork(config)
    net.add_node(Node(0, 0, 0, config))
    net.add_node(Node(1, 50, 0, config))
    net.update_links()
    
    n1 = net.nodes[1]
    n1.queue = [Packet(0, 1, 0)] * 50
    n1.update_queue_history()
    
    cpqr = CPQR(net, config)
    pkt = Packet(src=0, dst=1, created_at=0.0)
    
    # Calculate penalty manually
    cp = cpqr.config.beta * (n1.predicted_queue_depth(cpqr.config.lambda_ewma) / cpqr.MAX_QUEUE_CAPACITY)
    assert cp <= cpqr.config.beta

def test_cpqr_in_flight_bounded():
    config = SimConfig()
    net = WirelessNetwork(config)
    cpqr = CPQR(net, config)
    for i in range(20000):
        cpqr._record_dispatch(Packet(src=0, dst=1, created_at=0.0), 0, 1, 1)
    assert len(cpqr.in_flight) <= 10000
