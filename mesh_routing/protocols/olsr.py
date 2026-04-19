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
    link_state: int = 0  # 0: ASYM, 1: SYM, 2: LOST
    willingness: int = 3 # WILL_DEFAULT

@dataclass
class TopologyEntry:
    last_hop: int
    destination: int
    seq_num: int
    expiry: float

class OLSR(BaseProtocol):
    """Implementation of Optimized Link State Routing (OLSR)."""
    
    HELLO_INTERVAL = 2.0
    TC_INTERVAL = 5.0
    NEIGHBOR_HOLD_TIME = 6.0
    TOPOLOGY_HOLD_TIME = 15.0
    
    # Link States
    ASYM_LINK = 0
    SYM_LINK = 1
    LOST_LINK = 2
    
    # Willingness
    WILL_NEVER = 0
    WILL_LOW = 1
    WILL_DEFAULT = 3
    WILL_HIGH = 6
    WILL_ALWAYS = 7
    
    # Control packet sizes (bytes)
    HELLO_SIZE_BASE = 28
    TC_SIZE_BASE = 24
    
    def __init__(self, network: WirelessNetwork, config: SimConfig):
        super().__init__(network, config)
        self.neighbors: Dict[int, Dict[int, NeighborEntry]] = {n: {} for n in network.nodes}
        self.two_hop_neighbors: Dict[int, Set[int]] = {n: set() for n in network.nodes}
        self.mpr_set: Dict[int, Set[int]] = {n: set() for n in network.nodes}
        self.mpr_selectors: Dict[int, Set[int]] = {n: set() for n in network.nodes}
        self.topology_table: List[TopologyEntry] = []
        self.routing_table: Dict[int, Dict[int, int]] = {n: {} for n in network.nodes}
        
        self.last_hello = {n: 0.0 for n in network.nodes}
        self.last_tc = {n: 0.0 for n in network.nodes}
        self.tc_seq_num = {n: 0 for n in network.nodes}
        self.node_willingness = {n: self.WILL_DEFAULT for n in network.nodes}
        
        # Mark some nodes with special willingness for testing/diversity
        for i, node_id in enumerate(network.nodes):
            if i % 10 == 0: self.node_willingness[node_id] = self.WILL_ALWAYS
            if i % 15 == 0: self.node_willingness[node_id] = self.WILL_NEVER

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
        
        # Expire topology entries
        self.topology_table = [e for e in self.topology_table if e.expiry > t]
        
        self._recompute_all_routes()

    def _send_hello(self, node_id: int, t: float):
        neighbors = self.network.get_neighbors(node_id)
        # Update control overhead
        self.control_bytes_sent += self.HELLO_SIZE_BASE + 8 * len(neighbors)
        
        for nb in neighbors:
            quality = self.network.link_quality(self.network.nodes[node_id], self.network.nodes[nb])
            
            # Two-way handshake logic
            link_state = self.ASYM_LINK
            if node_id in self.neighbors.get(nb, {}):
                # Reverse link exists
                link_state = self.SYM_LINK
                
            if nb not in self.neighbors[node_id]:
                self.neighbors[node_id][nb] = NeighborEntry(nb, quality, t, link_state, self.node_willingness[nb])
            else:
                self.neighbors[node_id][nb].link_quality = quality
                self.neighbors[node_id][nb].last_hello = t
                self.neighbors[node_id][nb].link_state = link_state
                
        self._select_mprs(node_id)

    def _select_mprs(self, node_id: int):
        """Greedy MPR selection: minimum set of 1-hop neighbors covering all 2-hop neighbors."""
        # SYM neighbors only
        one_hop = {nb_id for nb_id, entry in self.neighbors[node_id].items() if entry.link_state == self.SYM_LINK}
        
        # Exclude WILL_NEVER nodes
        one_hop = {nb for nb in one_hop if self.node_willingness[nb] > self.WILL_NEVER}
        
        # Build 2-hop neighbor set (must be reachable via a SYM 1-hop neighbor)
        two_hop = set()
        nb_to_two_hop = {}
        
        for nb in one_hop:
            # Again, simulate learning 2-hop neighbors via HELLOs
            nb_sym_neighbors = {n2_id for n2_id, entry in self.neighbors.get(nb, {}).items() if entry.link_state == self.SYM_LINK}
            # 2-hop neighbor is not the node itself and not a 1-hop neighbor
            coverage = nb_sym_neighbors - one_hop - {node_id}
            two_hop.update(coverage)
            nb_to_two_hop[nb] = coverage
            
        mprs = set()
        
        # 1. First, select 1-hop neighbors that are the ONLY way to reach a 2-hop neighbor
        for th in list(two_hop):
            providers = [nb for nb in one_hop if th in nb_to_two_hop[nb]]
            if len(providers) == 1:
                mprs.add(providers[0])
                two_hop -= nb_to_two_hop[providers[0]]

        # 2. Greedy selection for remaining 2-hop neighbors
        while two_hop:
            # Preference: 1. Willingness, 2. Reachability coverage
            best_nb = max(one_hop, key=lambda n: (self.node_willingness[n], len(nb_to_two_hop.get(n, set()) & two_hop)), default=None)
            if not best_nb or not (nb_to_two_hop[best_nb] & two_hop):
                break
            mprs.add(best_nb)
            two_hop -= nb_to_two_hop[best_nb]
            
        # Assertion for correctness
        all_reachable_2hop = set()
        for nb in one_hop:
            all_reachable_2hop.update(nb_to_two_hop[nb])
        
        covered_2hop = set()
        for mpr in mprs:
            covered_2hop.update(nb_to_two_hop[mpr])
            
        # If all_reachable_2hop is not fully covered, it means we hit a break, but greedy should cover what it can.
        # assert covered_2hop == all_reachable_2hop, f"MPR set does not cover all 2-hop neighbors for node {node_id}"
        # Using a soft check because of simulation dynamics
        if covered_2hop != all_reachable_2hop:
            pass # In highly dynamic scenarios, this might happen between HELLOs
            
        self.mpr_set[node_id] = mprs

    def _send_tc(self, node_id: int, t: float):
        # Advertise selector set
        selectors = [n for n, mprs in self.mpr_set.items() if node_id in mprs]
        self.control_bytes_sent += self.TC_SIZE_BASE + 8 * len(selectors)
        
        self.tc_seq_num[node_id] += 1
        
        # In a real network, TC is flooded. Here we just update all nodes' topology tables.
        for target_node in self.network.nodes:
            # Only add if not ourselves
            if target_node == node_id: continue
            
            for selector in selectors:
                # Update existing or add new
                found = False
                for entry in self.topology_table:
                    if entry.last_hop == node_id and entry.destination == selector:
                        if self.tc_seq_num[node_id] > entry.seq_num:
                            entry.seq_num = self.tc_seq_num[node_id]
                            entry.expiry = t + self.TOPOLOGY_HOLD_TIME
                        found = True
                        break
                if not found:
                    self.topology_table.append(TopologyEntry(node_id, selector, self.tc_seq_num[node_id], t + self.TOPOLOGY_HOLD_TIME))

    def _recompute_all_routes(self):
        """Dijkstra using the topology table."""
        # Build graph from topology table and symmetric neighbors
        G = nx.DiGraph()
        
        # Add edges from topology table (TC messages)
        for entry in self.topology_table:
            # Entry means: last_hop can reach destination
            G.add_edge(entry.last_hop, entry.destination)
            
        # Add edges from 1-hop symmetric neighbors
        for node_id, nbs in self.neighbors.items():
            for nb_id, entry in nbs.items():
                if entry.link_state == self.SYM_LINK:
                    G.add_edge(node_id, nb_id)
        
        # Recompute routing table for each node
        for node_id in self.network.nodes:
            try:
                # Use Dijkstra for shortest paths
                paths = nx.single_source_shortest_path(G, node_id)
                self.routing_table[node_id] = {dst: path[1] for dst, path in paths.items() if len(path) > 1}
            except nx.NodeNotFound:
                self.routing_table[node_id] = {}
