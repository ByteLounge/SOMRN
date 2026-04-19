from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional
import networkx as nx
from protocols.base import BaseProtocol
from core.packet import Packet
from core.network import WirelessNetwork
from config import SimConfig

@dataclass
class NeighborEntry:
    node_id: int
    link_quality: float
    last_hello: float

class OLSR(BaseProtocol):
    """Implementation of Optimized Link State Routing (OLSR)."""
    
    HELLO_INTERVAL = 2.0
    TC_INTERVAL = 5.0
    NEIGHBOR_HOLD_TIME = 6.0
    
    def __init__(self, network: WirelessNetwork, config: SimConfig):
        super().__init__(network, config)
        self.neighbors: Dict[int, Dict[int, NeighborEntry]] = {n: {} for n in network.nodes}
        self.two_hop_neighbors: Dict[int, Dict[int, Set[int]]] = {n: {} for n in network.nodes}
        self.mpr_set: Dict[int, Set[int]] = {n: set() for n in network.nodes}
        self.topology_map = nx.DiGraph()
        self.routing_table: Dict[int, Dict[int, int]] = {n: {} for n in network.nodes}
        
        self.last_hello = {n: 0.0 for n in network.nodes}
        self.last_tc = {n: 0.0 for n in network.nodes}

    @property
    def name(self) -> str:
        return "OLSR"

    def get_next_hop(self, node_id: int, packet: Packet) -> int:
        dst = packet.dst
        if dst in self.routing_table[node_id]:
            return self.routing_table[node_id][dst]
        return -1

    def on_link_change(self, changed_edges: List):
        # OLSR relies on periodic HELLOs, but we can speed up reaction
        self._recompute_all_routes()

    def on_timestep(self, t: float):
        for node_id in self.network.nodes:
            # Send HELLO
            if t - self.last_hello[node_id] >= self.HELLO_INTERVAL:
                self._send_hello(node_id, t)
                self.last_hello[node_id] = t
                
            # Send TC if MPR
            if t - self.last_tc[node_id] >= self.TC_INTERVAL:
                is_mpr_of_someone = any(node_id in mprs for mprs in self.mpr_set.values())
                if is_mpr_of_someone:
                    self._send_tc(node_id, t)
                self.last_tc[node_id] = t
                
        # Expire neighbors
        for node_id in self.neighbors:
            expired = [nb for nb, entry in self.neighbors[node_id].items() if t - entry.last_hello > self.NEIGHBOR_HOLD_TIME]
            for nb in expired:
                del self.neighbors[node_id][nb]
                if nb in self.two_hop_neighbors[node_id]:
                    del self.two_hop_neighbors[node_id][nb]
        
        self._recompute_all_routes()

    def _send_hello(self, node_id: int, t: float):
        self.control_bytes_sent += 28
        neighbors = self.network.get_neighbors(node_id)
        for nb in neighbors:
            quality = self.network.link_quality(self.network.nodes[node_id], self.network.nodes[nb])
            if nb not in self.neighbors[node_id]:
                self.neighbors[node_id][nb] = NeighborEntry(nb, quality, t)
            else:
                self.neighbors[node_id][nb].link_quality = quality
                self.neighbors[node_id][nb].last_hello = t
                
        self._select_mprs(node_id)

    def _select_mprs(self, node_id: int):
        """Greedy MPR selection."""
        # This is a simplification. Real OLSR shares 1-hop neighbors in HELLO to learn 2-hop.
        # We'll use the network object to simulate that knowledge exchange.
        one_hop = set(self.neighbors[node_id].keys())
        two_hop = set()
        nb_to_two_hop = {}
        
        for nb in one_hop:
            nb_neighbors = set(self.network.get_neighbors(nb)) - one_hop - {node_id}
            two_hop.update(nb_neighbors)
            nb_to_two_hop[nb] = nb_neighbors
            
        mprs = set()
        while two_hop:
            # Pick neighbor that covers most uncovered 2-hop neighbors
            best_nb = max(one_hop, key=lambda n: len(nb_to_two_hop.get(n, set()) & two_hop), default=None)
            if not best_nb or not (nb_to_two_hop[best_nb] & two_hop):
                break
            mprs.add(best_nb)
            two_hop -= nb_to_two_hop[best_nb]
            
        self.mpr_set[node_id] = mprs

    def _send_tc(self, node_id: int, t: float):
        # Advertise selector set (nodes that picked me as MPR)
        selectors = [n for n, mprs in self.mpr_set.items() if node_id in mprs]
        self.control_bytes_sent += 8 + 4 * len(selectors)
        
        for selector in selectors:
            self.topology_map.add_edge(node_id, selector)
            self.topology_map.add_edge(selector, node_id)

    def _recompute_all_routes(self):
        # Add current neighbors to topology map for 1-hop reachability
        for node_id, nbs in self.neighbors.items():
            for nb in nbs:
                self.topology_map.add_edge(node_id, nb)
                
        for node_id in self.network.nodes:
            try:
                paths = nx.single_source_shortest_path(self.topology_map, node_id)
                self.routing_table[node_id] = {dst: path[1] for dst, path in paths.items() if len(path) > 1}
            except nx.NodeNotFound:
                self.routing_table[node_id] = {}
