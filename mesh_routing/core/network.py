import networkx as nx
import math
from typing import Dict, Tuple, List, Optional
from core.node import Node
from core.link import Link

class WirelessNetwork:
    """Manages the network graph, nodes, and links."""
    def __init__(self, config):
        self.config = config
        self.graph = nx.Graph()
        self.nodes: Dict[int, Node] = {}
        self.links: Dict[Tuple[int, int], Link] = {}
        self.time: float = 0.0

    def add_node(self, node: Node):
        """Adds a node to the network."""
        self.nodes[node.id] = node
        self.graph.add_node(node.id, pos=(node.x, node.y))

    def rssi(self, n1: Node, n2: Node) -> float:
        """Calculates RSSI between two nodes using log-distance path loss."""
        d = n1.distance_to(n2)
        if d == 0:
            return self.config.tx_power_dbm
        
        # Simplified Friis / Log-distance
        d0 = 1.0
        if d < d0:
            return self.config.tx_power_dbm
        
        path_loss = 10 * self.config.path_loss_exponent * math.log10(d / d0)
        return self.config.tx_power_dbm - path_loss

    def link_quality(self, n1: Node, n2: Node) -> float:
        """Computes link quality (0 to 1) based on RSSI."""
        r = self.rssi(n1, n2)
        if r < self.config.noise_floor_dbm:
            return 0.0
        # Normalize between noise floor and max expected RSSI (e.g., -30 dBm)
        q = (r - self.config.noise_floor_dbm) / (-30.0 - self.config.noise_floor_dbm)
        return max(0.0, min(1.0, q))

    def update_links(self):
        """Rebuilds edges based on current node positions."""
        self.graph.clear_edges()
        for i, n1 in self.nodes.items():
            for j, n2 in self.nodes.items():
                if i >= j:
                    continue
                d = n1.distance_to(n2)
                if d <= self.config.tx_range:
                    r = self.rssi(n1, n2)
                    if r >= self.config.noise_floor_dbm:
                        self.graph.add_edge(i, j)
                        link_key = (min(i, j), max(i, j))
                        if link_key not in self.links:
                            self.links[link_key] = Link(min(i, j), max(i, j))
                        link = self.links[link_key]
                        link.update(r, self.time)
                        n1.rssi_to[j] = r
                        n2.rssi_to[i] = r

    def get_neighbors(self, node_id: int) -> List[int]:
        """Returns list of neighbor IDs for a given node."""
        if node_id in self.graph:
            return list(self.graph.neighbors(node_id))
        return []

    def get_link(self, n1_id: int, n2_id: int) -> Optional[Link]:
        """Gets link object between two nodes."""
        link_key = (min(n1_id, n2_id), max(n1_id, n2_id))
        return self.links.get(link_key)

    def is_connected(self, src: int, dst: int) -> bool:
        """Checks if there's a path between src and dst."""
        if src in self.graph and dst in self.graph:
            return nx.has_path(self.graph, src, dst)
        return False

    def shortest_path(self, src: int, dst: int) -> List[int]:
        """Returns shortest path (sequence of node IDs)."""
        if self.is_connected(src, dst):
            return nx.shortest_path(self.graph, src, dst)
        return []

    def topology_snapshot(self) -> dict:
        """Returns graph snapshot for dashboard."""
        return {
            'nodes': [{'id': n.id, 'x': n.x, 'y': n.y} for n in self.nodes.values()],
            'edges': [{'source': u, 'target': v} for u, v in self.graph.edges()]
        }
