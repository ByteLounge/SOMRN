import pytest
from core.network import WirelessNetwork
from core.node import Node
from core.packet import Packet
from config import SimConfig
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR

def test_aodv_route_discovery():
    config = SimConfig(tx_range=100.0)
    net = WirelessNetwork(config)
    # Chain topology: 0 -- 1 -- 2 -- 3 -- 4
    for i in range(5):
        net.add_node(Node(i, i*80, 0, config))
    net.update_links()
    
    aodv = AODV(net, config)
    pkt = Packet(src=0, dst=4, created_at=0.0)
    
    # First call triggers discovery
    next_hop = aodv.get_next_hop(0, pkt)
    assert next_hop == -1
    
    # Discovery completes (simulated via direct calls in our simplified AODV)
    # In the real simulation loop, discovery happens across steps.
    # Here, _flood_rreq and _unicast_rrep are synchronous for testing.
    assert 4 in aodv.routing_tables[0]
    assert aodv.routing_tables[0][4].next_hop == 1

def test_cpqr_q_update():
    config = SimConfig()
    net = WirelessNetwork(config)
    net.add_node(Node(0, 0, 0, config))
    net.add_node(Node(1, 50, 0, config))
    net.update_links()
    
    cpqr = CPQR(net, config)
    pkt = Packet(src=0, dst=1, created_at=0.0)
    
    # Simulate packet flow
    _ = cpqr.get_next_hop(0, pkt)
    net.time = 1.0 # Advance time
    cpqr.on_packet_delivered(pkt)
    
    # Q-value should be updated from default 10.0
    # new_q = (1-0.1)*10 + 0.1*(1.0 + 0.9*0) = 9 + 0.1 = 9.1
    assert cpqr.q_table[0][1][1] == 9.1

def test_olsr_mpr_selection():
    config = SimConfig(tx_range=100.0)
    net = WirelessNetwork(config)
    # Star topology: 0 is center, 1-4 are neighbors, 5 is neighbor of 1
    net.add_node(Node(0, 100, 100, config))
    net.add_node(Node(1, 150, 100, config))
    net.add_node(Node(2, 50, 100, config))
    net.add_node(Node(3, 100, 150, config))
    net.add_node(Node(4, 100, 50, config))
    net.add_node(Node(5, 230, 100, config)) # Only connected to 1
    net.update_links()
    
    olsr = OLSR(net, config)
    olsr._send_hello(0, 0.0)
    
    # 0 should select 1 as MPR to cover 5
    assert 1 in olsr.mpr_set[0]
