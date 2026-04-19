import numpy as np
from typing import List, Dict, Type, Callable, Optional
from core.node import Node
from core.network import WirelessNetwork
from core.packet import Packet
from core.mobility import RandomWaypointMobility, GaussMarkovMobility
from protocols.base import BaseProtocol
from metrics.collector import MetricsCollector
from config import SimConfig

class SimulationEngine:
    """Core simulation engine that orchestrates the network, mobility, and protocols."""
    def __init__(self, 
                 protocol_class: Type[BaseProtocol], 
                 config: SimConfig, 
                 mobility_class: Type = RandomWaypointMobility):
        self.config = config
        self.rng = np.random.default_rng(config.seed)
        
        # Initialize network
        self.network = WirelessNetwork(config)
        for i in range(config.num_nodes):
            x = self.rng.uniform(0, config.area_size)
            y = self.rng.uniform(0, config.area_size)
            self.network.add_node(Node(i, x, y, config))
            
        self.network.update_links()
        
        # Initialize mobility
        self.mobility = mobility_class(list(self.network.nodes.values()), config)
        
        # Initialize protocol
        self.protocol = protocol_class(self.network, config)
        
        # Initialize metrics
        self.metrics = MetricsCollector()
        
        # Traffic flows: (src, dst)
        self.flows = []
        node_ids = list(self.network.nodes.keys())
        for _ in range(config.num_flows):
            src, dst = self.rng.choice(node_ids, 2, replace=False)
            self.flows.append((int(src), int(dst)))
            
        self.on_snapshot_cb: Optional[Callable] = None

    def run(self) -> MetricsCollector:
        """Runs the simulation for the configured duration."""
        n_steps = int(self.config.duration / self.config.time_step)
        
        for step in range(n_steps):
            t = step * self.config.time_step
            self.network.time = t
            
            # 1. Mobility step
            self.mobility.step(self.config.time_step)
            
            # 2. Network update
            old_edges = set(self.network.graph.edges())
            self.network.update_links()
            new_edges = set(self.network.graph.edges())
            
            # 3. Detect topology changes
            changed_edges = []
            for e in old_edges - new_edges:
                changed_edges.append((e[0], e[1], 'down'))
                self.metrics.on_route_break()
            for e in new_edges - old_edges:
                changed_edges.append((e[0], e[1], 'up'))
                
            if changed_edges:
                self.protocol.on_link_change(changed_edges)
                
            # 4. Protocol periodic update
            self.protocol.on_timestep(t)
            self.metrics.on_control(self.protocol.control_bytes_sent)
            self.protocol.control_bytes_sent = 0 # Reset for current step counting
            
            # 5. Traffic generation (Poisson arrival)
            for src, dst in self.flows:
                if self.rng.random() < self.config.packet_rate * self.config.time_step:
                    pkt = Packet(src=src, dst=dst, created_at=t, size=self.config.packet_size)
                    self.network.nodes[src].queue.append(pkt)
                    self.metrics.on_send(pkt, t)
                    
            # 6. Packet forwarding
            self._forward_all_packets(t)
            
            # 7. Node state updates
            for node in self.network.nodes.values():
                node.update_queue_history()
                
            # 8. Snapshots
            if step % int(self.config.snapshot_interval / self.config.time_step) == 0:
                snap = self.metrics.snapshot(t, window=self.config.snapshot_interval)
                if self.on_snapshot_cb:
                    self.on_snapshot_cb(t, snap)
                    
        return self.metrics

    def _forward_all_packets(self, t: float):
        """Simulates packet transmission across the network."""
        # We'll use a copy of the nodes' queues to avoid issues during modification
        for node_id, node in self.network.nodes.items():
            if not node.queue:
                continue
                
            # In a single time step, a node can process a limited number of packets
            # based on bandwidth. For simplicity, we process a reasonable amount.
            packets_to_process = node.queue[:]
            node.queue = []
            
            for pkt in packets_to_process:
                if pkt.dst == node_id:
                    # Packet delivered!
                    pkt.delivered = True
                    pkt.delivered_at = t
                    self.metrics.on_deliver(pkt, t)
                    if hasattr(self.protocol, 'on_packet_delivered'):
                        self.protocol.on_packet_delivered(pkt)
                    continue
                    
                if pkt.ttl <= 0:
                    self.metrics.on_drop(pkt, t, "TTL Expired")
                    if hasattr(self.protocol, 'on_packet_dropped'):
                        self.protocol.on_packet_dropped(pkt)
                    continue
                    
                next_hop = self.protocol.get_next_hop(node_id, pkt)
                
                if next_hop != -1 and next_hop in self.network.get_neighbors(node_id):
                    # Transmit
                    pkt.hop_count += 1
                    pkt.ttl -= 1
                    pkt.route.append(node_id)
                    self.network.nodes[next_hop].queue.append(pkt)
                    # Energy depletion
                    node.energy -= node.energy_cost_to_forward()
                    self.metrics.energy_consumed += node.energy_cost_to_forward()
                else:
                    # No route or link break
                    if next_hop == -1:
                        # Re-queue for next step (limited buffer)
                        if len(node.queue) < 100:
                            node.queue.append(pkt)
                        else:
                            self.metrics.on_drop(pkt, t, "Queue Overflow")
                            if hasattr(self.protocol, 'on_packet_dropped'):
                                self.protocol.on_packet_dropped(pkt)
                    else:
                        self.metrics.on_drop(pkt, t, "No Route")
                        if hasattr(self.protocol, 'on_packet_dropped'):
                            self.protocol.on_packet_dropped(pkt)

    def get_topology_for_dashboard(self) -> dict:
        return self.network.topology_snapshot()
