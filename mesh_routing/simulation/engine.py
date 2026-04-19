import numpy as np
from typing import Callable, List, Optional
from core.network import WirelessNetwork
from core.node import Node
from core.packet import Packet
from core.mobility import RandomWaypointMobility
from metrics.collector import MetricsCollector

class SimulationEngine:
    def __init__(self, protocol_class, config, mobility_class=RandomWaypointMobility):
        self.config = config
        self.rng = np.random.default_rng(config.seed)
        self.network = WirelessNetwork(config)
        self.metrics = MetricsCollector()
        
        # Build network nodes
        for i in range(config.num_nodes):
            x = self.rng.uniform(0, config.area_size)
            y = self.rng.uniform(0, config.area_size)
            self.network.add_node(Node(i, x, y, config))
            
        self.network.update_links()
        self.mobility = mobility_class(self.network.nodes, config, self.rng)
        self.protocol = protocol_class(self.network, config)
        
        # Traffic flows (src, dst)
        self.flows = []
        nodes_list = list(self.network.nodes.keys())
        while len(self.flows) < config.num_flows and len(nodes_list) >= 2:
            src, dst = self.rng.choice(nodes_list, 2, replace=False)
            self.flows.append((src, dst))
            
        self.on_snapshot: Optional[Callable] = None
        self.packet_rate_per_flow = config.packet_rate / max(1, config.num_flows)
        self.next_packet_times = {i: self.rng.exponential(1.0 / config.packet_rate) for i in range(len(self.flows))}

    def run(self) -> MetricsCollector:
        n_steps = int(self.config.duration / self.config.time_step)
        next_snapshot = self.config.snapshot_interval

        for step in range(n_steps):
            t = step * self.config.time_step
            self.network.time = t
            
            # 1. Mobility
            self.mobility.step(self.config.time_step)
            
            # 2. Links
            old_edges = set(self.network.graph.edges())
            self.network.update_links()
            new_edges = set(self.network.graph.edges())
            
            # 3. Protocol events
            broken_edges = old_edges - new_edges
            newly_formed = new_edges - old_edges
            changed = list(broken_edges) + list(newly_formed)
            
            if broken_edges:
                self.metrics.on_route_break()
                
            if changed:
                self.protocol.on_link_change(changed)
                
            self.protocol.on_timestep(t)
            
            # 5. Generate packets
            for i, flow in enumerate(self.flows):
                if t >= self.next_packet_times[i]:
                    src, dst = flow
                    pkt = Packet(src, dst, t, size=self.config.packet_size)
                    self.network.nodes[src].queue.append(pkt)
                    self.metrics.on_send(pkt, t)
                    
                    # Next arrival
                    inter_arrival = self.rng.exponential(1.0 / self.config.packet_rate)
                    self.next_packet_times[i] = t + inter_arrival

            # 6. Forward packets
            self._forward_all_packets(t)
            
            # 7. Queue history
            for node in self.network.nodes.values():
                node.update_queue_history()
                
            # 8. Metrics snapshot
            if t >= next_snapshot:
                snap = self.metrics.snapshot(t, self.config.snapshot_interval)
                self.metrics.snapshots.append(snap)
                if self.on_snapshot:
                    self.on_snapshot(t, snap)
                next_snapshot += self.config.snapshot_interval
                
        # Final snapshot at end
        snap = self.metrics.snapshot(self.config.duration, self.config.snapshot_interval)
        self.metrics.snapshots.append(snap)
        if self.on_snapshot:
            self.on_snapshot(self.config.duration, snap)
            
        return self.metrics

    def _forward_all_packets(self, t: float):
        # Gather all current queues to process (to avoid processing newly arrived packets in same timestep)
        to_process = {}
        for nid, node in self.network.nodes.items():
            to_process[nid] = list(node.queue)
            node.queue.clear()
            
        for nid, queue in to_process.items():
            node = self.network.nodes[nid]
            for pkt in queue:
                if pkt.hop_count >= pkt.ttl:
                    pkt.dropped = True
                    pkt.drop_reason = "TTL"
                    self.metrics.on_drop(pkt, t, "TTL")
                    if hasattr(self.protocol, 'on_packet_dropped'):
                        self.protocol.on_packet_dropped(pkt)
                    continue
                    
                next_hop = self.protocol.get_next_hop(nid, pkt)
                
                if next_hop == -1:
                    # Dropped or held
                    # Basic approach: just drop if no route
                    pkt.dropped = True
                    pkt.drop_reason = "NoRoute"
                    self.metrics.on_drop(pkt, t, "NoRoute")
                    continue
                    
                if next_hop == pkt.dst:
                    # Delivered
                    pkt.delivered = True
                    pkt.delivered_at = t
                    pkt.hop_count += 1
                    pkt.route.append(next_hop)
                    self.metrics.on_deliver(pkt, t)
                    if hasattr(self.protocol, 'on_packet_delivered'):
                        self.protocol.on_packet_delivered(pkt, t)
                else:
                    # Forwarded
                    if next_hop in self.network.nodes:
                        cost = node.energy_cost_to_forward()
                        node.energy -= cost
                        self.metrics.energy_consumed += cost
                        pkt.hop_count += 1
                        pkt.route.append(next_hop)
                        self.network.nodes[next_hop].queue.append(pkt)
                    else:
                        pkt.dropped = True
                        self.metrics.on_drop(pkt, t, "InvalidHop")
        
        # Account for control overhead per timestep
        if self.protocol.control_bytes_sent > 0:
            self.metrics.on_control(self.protocol.control_bytes_sent)
            self.protocol.control_bytes_sent = 0 # Reset counter after logging

    def get_topology_for_dashboard(self) -> dict:
        return self.network.topology_snapshot()
