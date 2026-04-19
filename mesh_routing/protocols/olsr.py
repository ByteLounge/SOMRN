from dataclasses import dataclass
from typing import Dict, List, Set, Tuple
from protocols.base import BaseProtocol
import networkx as nx

@dataclass
class NeighborEntry:
    node_id: int
    link_quality: float
    last_hello: float

@dataclass
class HelloMessage:
    src: int
    neighbors: List[int]

@dataclass
class TCMessage:
    src: int
    seq_num: int
    mpr_selectors: List[int]

class OLSR(BaseProtocol):
    def __init__(self, network, config):
        super().__init__(network, config)
        self.HELLO_INTERVAL = 2.0
        self.TC_INTERVAL = 5.0
        self.last_hello: Dict[int, float] = {n: 0.0 for n in network.nodes}
        self.last_tc: Dict[int, float] = {n: 0.0 for n in network.nodes}
        
        self.neighbors: Dict[int, Dict[int, NeighborEntry]] = {n: {} for n in network.nodes}
        self.mpr_set: Dict[int, Set[int]] = {n: set() for n in network.nodes}
        self.mpr_selectors: Dict[int, Set[int]] = {n: set() for n in network.nodes}
        
        self.topology_graph = nx.Graph()
        self.routing_table: Dict[int, Dict[int, int]] = {n: {} for n in network.nodes}
        self.tc_seq_nums: Dict[int, int] = {n: 0 for n in network.nodes}
        self.seen_tcs: Dict[int, Dict[int, int]] = {n: {} for n in network.nodes} # node -> {src -> seq}

    def get_next_hop(self, node_id: int, packet) -> int:
        if packet.dst in self.routing_table[node_id]:
            return self.routing_table[node_id][packet.dst]
        return -1

    def on_link_change(self, changed_edges: List[Tuple[int, int]]):
        # Reactive clearing not strictly OLSR, but helps simulator
        pass

    def on_timestep(self, t: float):
        self._send_hellos(t)
        self._compute_mprs()
        self._send_tcs(t)
        self._compute_routing_tables()

    def _send_hellos(self, t: float):
        for node in self.network.nodes:
            if t - self.last_hello[node] >= self.HELLO_INTERVAL:
                self.last_hello[node] = t
                nbs = list(self.neighbors[node].keys())
                msg = HelloMessage(node, nbs)
                self.control_bytes_sent += 28 + len(nbs) * 4
                
                for nb in self.network.get_neighbors(node):
                    if nb not in self.neighbors[nb]:
                        self.neighbors[nb][node] = NeighborEntry(node, 1.0, t)
                    else:
                        self.neighbors[nb][node].last_hello = t

    def _compute_mprs(self):
        # Simplified MPR selection: just select all neighbors for simplicity
        # Full MPR selection requires 2-hop knowledge, we approximate by selecting all for robustness in simulation
        for node in self.network.nodes:
            nbs = self.network.get_neighbors(node)
            self.mpr_set[node] = set(nbs)
            for nb in nbs:
                self.mpr_selectors[nb].add(node)

    def _send_tcs(self, t: float):
        for node in self.network.nodes:
            if len(self.mpr_selectors[node]) > 0:
                if t - self.last_tc[node] >= self.TC_INTERVAL:
                    self.last_tc[node] = t
                    self.tc_seq_nums[node] += 1
                    msg = TCMessage(node, self.tc_seq_nums[node], list(self.mpr_selectors[node]))
                    self.control_bytes_sent += 32 + len(msg.mpr_selectors) * 4
                    self._flood_tc(node, msg)

    def _flood_tc(self, current_node: int, msg: TCMessage):
        # Update global topology view (simulated centralized for OLSR routing table to avoid full message passing complex state)
        for selector in msg.mpr_selectors:
            self.topology_graph.add_edge(msg.src, selector)

    def _compute_routing_tables(self):
        # Rebuild routing tables from topology graph
        for node in self.network.nodes:
            if node in self.topology_graph:
                try:
                    paths = nx.single_source_shortest_path(self.topology_graph, node)
                    for dst, path in paths.items():
                        if len(path) > 1:
                            self.routing_table[node][dst] = path[1]
                except Exception:
                    pass
