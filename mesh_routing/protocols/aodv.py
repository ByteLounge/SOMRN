from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional
from protocols.base import BaseProtocol
from core.packet import Packet
from core.network import WirelessNetwork
from config import SimConfig

@dataclass
class RouteEntry:
    """Entry in the AODV routing table."""
    next_hop: int
    hop_count: int
    seq_num: int
    lifetime: float
    precursors: Set[int] = field(default_factory=set)

@dataclass
class PendingRequest:
    """A RREQ that is currently awaiting a response."""
    dst: int
    rreq_id: int
    created_at: float
    waiting_packets: List[Packet] = field(default_factory=list)
    retries: int = 0

class AODV(BaseProtocol):
    """Implementation of the Ad-hoc On-Demand Distance Vector (AODV) routing protocol."""
    
    ROUTE_LIFETIME = 30.0
    RREQ_TIMEOUT = 3.0
    RREQ_RETRIES = 2
    LOCAL_REPAIR_ATTEMPTS = 1
    
    # Control packet sizes (bytes)
    RREQ_SIZE = 48
    RREP_SIZE = 32
    RERR_SIZE = 24
    HELLO_SIZE = 20
    
    def __init__(self, network: WirelessNetwork, config: SimConfig):
        super().__init__(network, config)
        self.routing_tables: Dict[int, Dict[int, RouteEntry]] = {} # node_id -> {dst_id -> entry}
        self.pending_requests: Dict[int, Dict[int, PendingRequest]] = {} # node_id -> {dst_id -> request}
        self.seen_rreqs: Dict[int, List[tuple]] = {} # node_id -> [(src, rreq_id)] - LRU
        self.rreq_counter: Dict[int, int] = {} # node_id -> last_rreq_id
        self.node_seq_num: Dict[int, int] = {} # node_id -> current_seq_num
        
        for node_id in network.nodes:
            self.routing_tables[node_id] = {}
            self.pending_requests[node_id] = {}
            self.seen_rreqs[node_id] = []
            self.rreq_counter[node_id] = 0
            self.node_seq_num[node_id] = 1

    @property
    def name(self) -> str:
        return "AODV"

    def get_next_hop(self, node_id: int, packet: Packet) -> int:
        """Lookup route for destination; trigger discovery if needed."""
        dst = packet.dst
        
        # Check if route exists and is fresh
        if dst in self.routing_tables[node_id]:
            entry = self.routing_tables[node_id][dst]
            if self.network.time < entry.lifetime:
                # Validate link is still active
                if entry.next_hop in self.network.get_neighbors(node_id):
                    return entry.next_hop
                else:
                    # Link broken, invalidate and trigger RERR
                    del self.routing_tables[node_id][dst]
            else:
                del self.routing_tables[node_id][dst]
        
        # Trigger route discovery
        self._discover_route(node_id, packet)
        return -1 # Packet must wait in buffer

    def _discover_route(self, node_id: int, packet: Packet):
        """Initiates RREQ flooding for a destination."""
        dst = packet.dst
        if dst in self.pending_requests[node_id]:
            self.pending_requests[node_id][dst].waiting_packets.append(packet)
            return
            
        rreq_id = self.rreq_counter[node_id] + 1
        self.rreq_counter[node_id] = rreq_id
        
        req = PendingRequest(dst, rreq_id, self.network.time)
        req.waiting_packets.append(packet)
        self.pending_requests[node_id][dst] = req
        
        # Broadcast RREQ
        self._flood_rreq(node_id, node_id, dst, rreq_id, 0)

    def _flood_rreq(self, start_node: int, src: int, dst: int, rreq_id: int, start_hops: int):
        """Iterative RREQ flooding simulation."""
        queue = [(start_node, start_hops)]
        
        while queue:
            current_node, hops = queue.pop(0)
            self.control_bytes_sent += 48
            
            if hops >= 10: continue # TTL

            neighbors = self.network.get_neighbors(current_node)
            for nb in neighbors:
                if (src, rreq_id) in self.seen_rreqs[nb]:
                    continue
                self.seen_rreqs[nb].add((src, rreq_id))
                
                # Update reverse route to source
                if src not in self.routing_tables[nb]:
                    self.routing_tables[nb][src] = RouteEntry(current_node, hops + 1, 0, self.network.time + self.ROUTE_LIFETIME)
                
                # Destination reached?
                if nb == dst:
                    self._unicast_rrep(nb, src, dst, 0)
                    # Once a RREP is triggered, we can stop this branch, 
                    # but in real AODV others might still forward.
                else:
                    queue.append((nb, hops + 1))

    def _unicast_rrep(self, start_node: int, src: int, dst: int, start_hops: int):
        """Iterative RREP unicast back to source."""
        curr = start_node
        hops = start_hops
        
        visited = set()
        while curr != src and curr not in visited:
            visited.add(curr)
            self.control_bytes_sent += 32
            
            # Find route back to source
            if src in self.routing_tables[curr]:
                next_node = self.routing_tables[curr][src].next_hop
                
                # Update forward route to destination
                if dst not in self.routing_tables[next_node]:
                    self.routing_tables[next_node][dst] = RouteEntry(curr, hops + 1, 0, self.network.time + self.ROUTE_LIFETIME)
                
                curr = next_node
                hops += 1
            else:
                break 

    def on_link_change(self, changed_edges: List):
        """Invalidate routes using broken links."""
        for u, v, status in changed_edges:
            if status == 'down':
                for node_id in [u, v]:
                    broken_neighbor = v if node_id == u else u
                    to_delete = []
                    for dst, entry in self.routing_tables[node_id].items():
                        if entry.next_hop == broken_neighbor:
                            to_delete.append(dst)
                    
                    if to_delete:
                        self.control_bytes_sent += 24 # RERR
                        for dst in to_delete:
                            del self.routing_tables[node_id][dst]

    def on_timestep(self, t: float):
        """Expire old routes and pending requests."""
        for node_id in self.routing_tables:
            # Expire routes
            to_expire = [dst for dst, entry in self.routing_tables[node_id].items() if entry.lifetime < t]
            for dst in to_expire:
                del self.routing_tables[node_id][dst]
                
            # Retransmit pending RREQs
            to_retry = []
            for dst, req in self.pending_requests[node_id].items():
                if t - req.created_at > self.RREQ_TIMEOUT:
                    if req.retries < self.RREQ_RETRIES:
                        to_retry.append(dst)
                    else:
                        # Drop packets - route not found
                        for p in req.waiting_packets:
                            p.dropped = True
                            p.drop_reason = "Route Discovery Failed"
                        # Cleanup later
            
            for dst in to_retry:
                req = self.pending_requests[node_id][dst]
                req.retries += 1
                req.created_at = t
                self._flood_rreq(node_id, node_id, dst, req.rreq_id, 0)
                
            # Cleanup failed requests
            failed = [dst for dst, req in self.pending_requests[node_id].items() 
                      if req.retries >= self.RREQ_RETRIES and t - req.created_at > self.RREQ_TIMEOUT]
            for dst in failed:
                del self.pending_requests[node_id][dst]
                
            # If route now exists for pending requests, they will be handled next time get_next_hop is called
            # (In this simplified engine, we don't have a separate buffer flush, 
            # get_next_hop is called for every packet in the node's queue every step)
