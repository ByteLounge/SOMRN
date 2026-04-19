import pytest
from config import SimConfig
from core.network import WirelessNetwork
from core.node import Node
from core.packet import Packet
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR

@pytest.fixture
def static_network():
    config = SimConfig(tx_range=15.0)
    net = WirelessNetwork(config)
    for i in range(5):
        net.add_node(Node(i, i * 10.0, 0.0, config))
    net.update_links()
    return net, config

def test_aodv_route_discovery(static_network):
    net, config = static_network
    aodv = AODV(net, config)
    
    pkt = Packet(src=0, dst=4, created_at=0.0)
    next_hop = aodv.get_next_hop(0, pkt)
    
    assert next_hop == -1 # Init RREQ
    
    # Simulate timestep to broadcast
    aodv.on_timestep(0.1)
    
    # The RREQ should be propagated manually or via engine. In a real engine, engine does it.
    # For test, we check if pending request created
    assert 4 in aodv.pending_requests[0]

def test_aodv_invalidation(static_network):
    net, config = static_network
    aodv = AODV(net, config)
    # Manually add route
    aodv.routes[0][1] = aodv.routes.get(0, {}).get(1) # Fake
    from protocols.aodv import RouteEntry
    aodv.routes[0][1] = RouteEntry(next_hop=1, hop_count=1, seq_num=1, lifetime=100.0)
    
    aodv.on_link_change([(0, 1)])
    assert 1 not in aodv.routes[0]

def test_olsr_mpr(static_network):
    net, config = static_network
    olsr = OLSR(net, config)
    olsr._compute_mprs()
    # Node 0's neighbor is 1
    assert 1 in olsr.mpr_set[0]

def test_cpqr_q_value(static_network):
    net, config = static_network
    cpqr = CPQR(net, config)
    
    pkt = Packet(src=0, dst=1, created_at=0.0)
    pkt.packet_id = "test1"
    
    next_hop = cpqr.get_next_hop(0, pkt)
    # Assume 1 is chosen
    cpqr.in_flight["test1"] = {'node': 0, 'dst': 1, 'via': 1, 'sent_at': 0.0}
    cpqr.on_packet_delivered(pkt, 1.0)
    
    # Q should change from 10.0
    assert cpqr.Q[0][1][1] != 10.0

def test_cpqr_link_lifetime(static_network):
    net, config = static_network
    cpqr = CPQR(net, config)
    assert cpqr._link_safe(0, 1) == True # Stable initially
