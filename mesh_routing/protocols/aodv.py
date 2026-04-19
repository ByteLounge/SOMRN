from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple
from protocols.base import BaseProtocol

@dataclass
class RouteEntry:
    next_hop: int
    hop_count: int
    seq_num: int
    lifetime: float

@dataclass
class PendingRequest:
    dst: int
    rreq_id: int
    created_at: float
    waiting_packets: list = field(default_factory=list)
    retries: int = 0

class AODV(BaseProtocol):
    def __init__(self, network, config):
        super().__init__(network, config)
        self.routes: Dict[int, Dict[int, RouteEntry]] = {n: {} for n in network.nodes}
        self.pending_requests: Dict[int, Dict[int, PendingRequest]] = {n: {} for n in network.nodes}
        self.seq_nums: Dict[int, int] = {n: 1 for n in network.nodes}
        self.rreq_id: int = 1
        self.seen_rreqs: Set[Tuple[int, int]] = set() # (src, rreq_id)
        
        # Constants
        self.ROUTE_LIFETIME = 30.0
        self.RREQ_TIMEOUT = 3.0
        self.RREQ_RETRIES = 2
        
        self.RREQ_SIZE = 48
        self.RREP_SIZE = 32
        self.RERR_SIZE = 24

    def get_next_hop(self, node_id: int, packet) -> int:
        dst = packet.dst
        if dst in self.routes[node_id]:
            entry = self.routes[node_id][dst]
            if entry.lifetime > self.network.time:
                # Refresh lifetime on use
                entry.lifetime = self.network.time + self.ROUTE_LIFETIME
                return entry.next_hop
            else:
                # Expired
                del self.routes[node_id][dst]
                
        # Needs route discovery
        if dst not in self.pending_requests[node_id]:
            self._initiate_rreq(node_id, dst)
        
        req = self.pending_requests[node_id][dst]
        req.waiting_packets.append(packet)
        return -1 # Drop or hold, engine handles returning -1

    def _initiate_rreq(self, src: int, dst: int):
        self.seq_nums[src] += 1
        rreq_id = self.rreq_id
        self.rreq_id += 1
        self.pending_requests[src][dst] = PendingRequest(dst, rreq_id, self.network.time)
        self.seen_rreqs.add((src, rreq_id))
        
        # Broadcast RREQ to neighbors
        for nb in self.network.get_neighbors(src):
            self.control_bytes_sent += self.RREQ_SIZE
            self._process_rreq(nb, src, dst, src, 1, self.seq_nums[src], rreq_id)

    def _process_rreq(self, node: int, src: int, dst: int, prev_hop: int, hop_count: int, src_seq: int, rreq_id: int):
        if (src, rreq_id) in self.seen_rreqs:
            return
        self.seen_rreqs.add((src, rreq_id))
        
        # Setup reverse route
        if src not in self.routes[node] or self.routes[node][src].seq_num < src_seq:
            self.routes[node][src] = RouteEntry(prev_hop, hop_count, src_seq, self.network.time + self.ROUTE_LIFETIME)
            
        if node == dst or (dst in self.routes[node] and self.routes[node][dst].lifetime > self.network.time):
            # Send RREP
            dst_seq = self.seq_nums[dst] if node == dst else self.routes[node][dst].seq_num
            target_hop = 0 if node == dst else self.routes[node][dst].hop_count
            self.control_bytes_sent += self.RREP_SIZE
            self._process_rrep(prev_hop, src, dst, node, target_hop + 1, dst_seq)
        else:
            # Forward RREQ
            for nb in self.network.get_neighbors(node):
                if nb != prev_hop:
                    self.control_bytes_sent += self.RREQ_SIZE
                    self._process_rreq(nb, src, dst, node, hop_count + 1, src_seq, rreq_id)

    def _process_rrep(self, node: int, src: int, dst: int, prev_hop: int, hop_count: int, dst_seq: int):
        if dst not in self.routes[node] or self.routes[node][dst].seq_num < dst_seq:
            self.routes[node][dst] = RouteEntry(prev_hop, hop_count, dst_seq, self.network.time + self.ROUTE_LIFETIME)
            
        if node == src:
            if dst in self.pending_requests[node]:
                # Packets can now be forwarded on next timestep
                del self.pending_requests[node][dst]
        else:
            # Forward RREP along reverse path
            if src in self.routes[node]:
                next_hop = self.routes[node][src].next_hop
                self.control_bytes_sent += self.RREP_SIZE
                self._process_rrep(next_hop, src, dst, node, hop_count + 1, dst_seq)

    def on_link_change(self, changed_edges: List[Tuple[int, int]]):
        broken_links = set(changed_edges)
        for node in self.routes:
            to_remove = []
            for dst, entry in self.routes[node].items():
                if (node, entry.next_hop) in broken_links or (entry.next_hop, node) in broken_links:
                    to_remove.append(dst)
            for dst in to_remove:
                del self.routes[node][dst]
                self.control_bytes_sent += self.RERR_SIZE # Broadcast RERR approx

    def on_timestep(self, t: float):
        # Retry or timeout pending RREQs
        for node, reqs in list(self.pending_requests.items()):
            to_remove = []
            for dst, req in list(reqs.items()):
                if t - req.created_at > self.RREQ_TIMEOUT:
                    if req.retries < self.RREQ_RETRIES:
                        req.retries += 1
                        req.created_at = t
                        self._initiate_rreq(node, dst)
                    else:
                        # Drop waiting packets? The engine handles dropping if unroutable
                        to_remove.append(dst)
            for dst in to_remove:
                del self.pending_requests[node][dst]
