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
        
        # Increment own sequence number
        self.node_seq_num[node_id] += 1
        
        req = PendingRequest(dst, rreq_id, self.network.time)
        req.waiting_packets.append(packet)
        self.pending_requests[node_id][dst] = req
        
        # Broadcast RREQ
        # Destination sequence number: if we have a stale one, use it, else 0
        dst_seq = 0
        if dst in self.routing_tables[node_id]:
            dst_seq = self.routing_tables[node_id][dst].seq_num
            
        self._flood_rreq(node_id, node_id, dst, rreq_id, 0, self.node_seq_num[node_id], dst_seq)

    def _add_seen_rreq(self, node_id: int, src: int, rreq_id: int):
        """Adds to seen_rreqs with LRU eviction."""
        pair = (src, rreq_id)
        if pair in self.seen_rreqs[node_id]:
            self.seen_rreqs[node_id].remove(pair)
        self.seen_rreqs[node_id].append(pair)
        if len(self.seen_rreqs[node_id]) > 10000:
            self.seen_rreqs[node_id].pop(0)

    def _flood_rreq(self, start_node: int, src: int, dst: int, rreq_id: int, start_hops: int, src_seq: int, dst_seq: int):
        """Iterative RREQ flooding simulation with sequence number checks."""
        queue = [(start_node, start_hops)]
        
        while queue:
            current_node, hops = queue.pop(0)
            
            if hops >= 15: continue # TTL

            neighbors = self.network.get_neighbors(current_node)
            for nb in neighbors:
                self.control_bytes_sent += self.RREQ_SIZE
                
                if (src, rreq_id) in self.seen_rreqs[nb]:
                    continue
                self._add_seen_rreq(nb, src, rreq_id)
                
                # Update reverse route to source
                # Only update if new seq_num is higher or (equal and fewer hops)
                update_reverse = False
                if src not in self.routing_tables[nb]:
                    update_reverse = True
                else:
                    old_entry = self.routing_tables[nb][src]
                    if src_seq > old_entry.seq_num:
                        update_reverse = True
                    elif src_seq == old_entry.seq_num and (hops + 1) < old_entry.hop_count:
                        update_reverse = True
                
                if update_reverse:
                    self.routing_tables[nb][src] = RouteEntry(
                        next_hop=current_node,
                        hop_count=hops + 1,
                        seq_num=src_seq,
                        lifetime=self.network.time + self.ROUTE_LIFETIME,
                        precursors=set()
                    )
                
                # Destination reached?
                if nb == dst:
                    # Update destination sequence number if higher
                    self.node_seq_num[nb] = max(self.node_seq_num[nb], dst_seq + 1)
                    self._unicast_rrep(nb, src, dst, 0, self.node_seq_num[nb])
                # Intermediate node with fresh route? (Gratuitous RREP)
                elif dst in self.routing_tables[nb]:
                    entry = self.routing_tables[nb][dst]
                    if entry.seq_num >= dst_seq and self.network.time < entry.lifetime:
                        # Send RREP back to source
                        self._unicast_rrep(nb, src, dst, entry.hop_count, entry.seq_num)
                        # Gratuitous RREP also notifies destination
                        # In simplified model, we just ensure destination route back to source is updated
                else:
                    queue.append((nb, hops + 1))

    def _unicast_rrep(self, start_node: int, src: int, dst: int, start_hops: int, dst_seq: int):
        """Iterative RREP unicast back to source with sequence number checks and precursors."""
        curr = start_node
        hops = start_hops
        
        visited = set()
        while curr != src and curr not in visited:
            visited.add(curr)
            self.control_bytes_sent += self.RREP_SIZE
            
            # Find route back to source
            if src in self.routing_tables[curr]:
                next_node = self.routing_tables[curr][src].next_hop
                
                # Update forward route to destination in the next node
                update_forward = False
                if dst not in self.routing_tables[next_node]:
                    update_forward = True
                else:
                    old_entry = self.routing_tables[next_node][dst]
                    if dst_seq > old_entry.seq_num:
                        update_forward = True
                    elif dst_seq == old_entry.seq_num and (hops + 1) < old_entry.hop_count:
                        update_forward = True
                
                if update_forward:
                    self.routing_tables[next_node][dst] = RouteEntry(
                        next_hop=curr,
                        hop_count=hops + 1,
                        seq_num=dst_seq,
                        lifetime=self.network.time + self.ROUTE_LIFETIME,
                        precursors=set()
                    )
                
                # Add next_node to precursor list of curr for destination dst
                if dst in self.routing_tables[curr]:
                    self.routing_tables[curr][dst].precursors.add(next_node)
                
                curr = next_node
                hops += 1
            else:
                break

    def _send_rerr(self, node_id: int, broken_dsts: List[int]):
        """Sends RERR to precursors for broken destinations."""
        if not broken_dsts:
            return
            
        self.control_bytes_sent += self.RERR_SIZE
        # In this simulation, we simplify precursor notification by immediately invalidating 
        # routes in those precursor nodes.
        for dst in broken_dsts:
            if dst in self.routing_tables[node_id]:
                precursors = self.routing_tables[node_id][dst].precursors
                for pre in precursors:
                    if dst in self.routing_tables[pre] and self.routing_tables[pre][dst].next_hop == node_id:
                        # Recursively notify their precursors? 
                        # Real AODV broadcasts RERR. Here we just invalidate.
                        del self.routing_tables[pre][dst]
                del self.routing_tables[node_id][dst]

    def on_link_change(self, changed_edges: List):
        """Invalidate routes using broken links, attempt local repair, and notify precursors."""
        for u, v, status in changed_edges:
            if status == 'down':
                for node_id in [u, v]:
                    broken_neighbor = v if node_id == u else u
                    affected_dsts = []
                    for dst, entry in self.routing_tables[node_id].items():
                        if entry.next_hop == broken_neighbor:
                            affected_dsts.append(dst)
                    
                    if not affected_dsts:
                        continue
                        
                    # Attempt Local Repair for each affected destination
                    remaining_dsts = []
                    for dst in affected_dsts:
                        # Local repair is usually only for destinations 'close' to the break
                        # but here we follow the instruction: re-initiate RREQ
                        if self.routing_tables[node_id][dst].hop_count < 5: # Threshold for local repair
                            rreq_id = self.rreq_counter[node_id] + 1
                            self.rreq_counter[node_id] = rreq_id
                            self.node_seq_num[node_id] += 1
                            
                            # Use incremented seq_num for local repair
                            self._flood_rreq(node_id, node_id, dst, rreq_id, 0, self.node_seq_num[node_id], self.routing_tables[node_id][dst].seq_num + 1)
                        else:
                            remaining_dsts.append(dst)
                    
                    # Notify precursors for those that failed local repair
                    self._send_rerr(node_id, remaining_dsts)

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
            
            for dst in to_retry:
                req = self.pending_requests[node_id][dst]
                req.retries += 1
                req.created_at = t
                
                dst_seq = 0
                if dst in self.routing_tables[node_id]:
                    dst_seq = self.routing_tables[node_id][dst].seq_num
                
                self._flood_rreq(node_id, node_id, dst, req.rreq_id, 0, self.node_seq_num[node_id], dst_seq)
                
            # Cleanup failed requests
            failed = [dst for dst, req in self.pending_requests[node_id].items() 
                      if req.retries >= self.RREQ_RETRIES and t - req.created_at > self.RREQ_TIMEOUT]
            for dst in failed:
                del self.pending_requests[node_id][dst]
