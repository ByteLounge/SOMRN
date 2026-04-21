import networkx as nx
import math
from typing import Dict, Tuple, List, Optional
from core.node import Node
from core.link import Link
from config import SimConfig

class WirelessNetwork:
    """Manages the network topology and physical layer simulation."""
    def __init__(self, config: SimConfig):
        self.config = config
        self.graph = nx.Graph()
        self.nodes: Dict[int, Node] = {}
        self.links: Dict[Tuple[int, int], Link] = {}
        self.time: float = 0.0

    def add_node(self, node: Node) -> None:
        """Adds a node to the network."""
        self.nodes[node.id] = node
        self.graph.add_node(node.id)

    def rssi(self, n1: Node, n2: Node) -> float:
        """Calculates received signal strength using simplified path loss model."""
        d = max(1.0, n1.distance_to(n2)) # Avoid log(0)
        # Simplified Friis / log-distance path loss
        # Pr = Pt - 10 * n * log10(d) - constant
        # For simplicity, calibrating such that at tx_range, rssi = noise_floor
        # constant = tx_power - noise_floor - 10 * n * log10(tx_range)
        constant = self.config.tx_power_dbm - self.config.noise_floor_dbm - 10 * self.config.path_loss_exponent * math.log10(self.config.tx_range)
        
        rssi_val = self.config.tx_power_dbm - 10 * self.config.path_loss_exponent * math.log10(d) - constant
        return rssi_val

    def link_quality(self, n1: Node, n2: Node) -> float:
        """Calculates link quality (0.0 to 1.0) based on RSSI and noise floor."""
        rssi_val = self.rssi(n1, n2)
        margin = rssi_val - self.config.noise_floor_dbm
        
        if margin <= 0:
            return 0.0
        elif margin >= 20: # 20dB fade margin gives 100% quality
            return 1.0
        else:
            return margin / 20.0

    def update_links(self) -> None:
        """Updates all links in the network based on current node positions."""
        self.graph.clear_edges()
        
        node_ids = list(self.nodes.keys())
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                id1 = node_ids[i]
                id2 = node_ids[j]
                n1 = self.nodes[id1]
                n2 = self.nodes[id2]
                
                dist = n1.distance_to(n2)
                if dist <= self.config.tx_range:
                    rssi_val = self.rssi(n1, n2)
                    quality = self.link_quality(n1, n2)
                    
                    if quality > 0.01: # Threshold for active link
                        self.graph.add_edge(id1, id2, weight=dist)
                        
                        link_key = tuple(sorted((id1, id2)))
                        if link_key not in self.links:
                            self.links[link_key] = Link(link_key[0], link_key[1])
                            
                        self.links[link_key].update(rssi_val, self.time)
                        self.links[link_key].quality = quality
                        
                        # Update node RSSI caches
                        n1.rssi_to[id2] = rssi_val
                        n2.rssi_to[id1] = rssi_val

    def get_neighbors(self, node_id: int) -> List[int]:
        """Returns a list of neighbor node IDs for a given node."""
        if self.graph.has_node(node_id):
            return list(self.graph.neighbors(node_id))
        return []

    def get_link(self, n1_id: int, n2_id: int) -> Optional[Link]:
        """Returns the Link object between two nodes if it exists."""
        link_key = tuple(sorted((n1_id, n2_id)))
        return self.links.get(link_key)

    def is_connected(self, src: int, dst: int) -> bool:
        """Checks if a path exists between src and dst."""
        try:
            return nx.has_path(self.graph, src, dst)
        except nx.NodeNotFound:
            return False

    def shortest_path(self, src: int, dst: int) -> List[int]:
        """Returns the shortest path (list of node IDs) or empty list if no path."""
        try:
            return nx.shortest_path(self.graph, src, dst)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def topology_snapshot(self) -> Dict:
        """Returns a serializable snapshot of the current topology for the dashboard."""
        snapshot = {
            'nodes': [
                {
                    'id': n.id, 
                    'x': n.x, 
                    'y': n.y, 
                    'energy': n.energy,
                    'queue_depth_pct': len(n.queue) / self.config.max_queue_capacity,
                    'queue_len': len(n.queue)
                } for n in self.nodes.values()
            ],
            'edges': []
        }
        for u, v in self.graph.edges():
            link = self.get_link(u, v)
            quality = link.quality if link else 0.0
            
            # Add link prediction data
            llt = float('inf')
            if link:
                llt = link.predicted_lifetime(self.config.time_step, self.config.noise_floor_dbm + 5)
                
            u_node = self.nodes[u]
            v_node = self.nodes[v]
            
            snapshot['edges'].append({
                'source': u, 
                'target': v, 
                'quality': quality,
                'llt': llt,
                'src_queue_pct': len(u_node.queue) / self.config.max_queue_capacity,
                'tgt_queue_pct': len(v_node.queue) / self.config.max_queue_capacity
            })
        return snapshot
