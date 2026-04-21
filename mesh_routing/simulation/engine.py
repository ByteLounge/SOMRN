import numpy as np
import logging
import networkx as nx
import time
from typing import List, Dict, Type, Callable, Optional, Set
from core.node import Node
from core.network import WirelessNetwork
from core.packet import Packet
from core.mobility import RandomWaypointMobility, GaussMarkovMobility
from protocols.base import BaseProtocol
from metrics.collector import MetricsCollector
from config import SimConfig

logger = logging.getLogger("mesh_routing.simulation.engine")

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
        self.metrics = MetricsCollector(config.num_nodes)
        self.metrics.net = self.network # For energy calculation in snapshots
        
        # Traffic flows: (src, dst)
        self.flows = []
        node_ids = list(self.network.nodes.keys())
        for _ in range(config.num_flows):
            src, dst = self.rng.choice(node_ids, 2, replace=False)
            self.flows.append((int(src), int(dst)))
            
        # Next packet generation times per flow
        self.next_packet_times = [self.rng.exponential(1.0 / config.packet_rate) for _ in range(config.num_flows)]
        
        self.on_snapshot_cb: Optional[Callable] = None
        self.on_step_cb: Optional[Callable] = None
        self.packet_positions = [] # For dashboard animation
        
        # BUG 2 State tracking
        self._in_partition: bool = False
        self._dead_nodes: set = set()
        self.WARMUP_PERIOD: float = 10.0
        self.time = 0.0

    def run(self, real_time: bool = False) -> MetricsCollector:
        """Runs the simulation for the configured duration."""
        n_steps = int(self.config.duration / self.config.time_step)
        
        for step in range(n_steps):
            t = step * self.config.time_step
            self.time = t
            self.network.time = t
            self.packet_positions = [] # Reset animations
            
            # 1. Mobility step
            self.mobility.step(self.config.time_step)
            
            # 2. Network update
            old_edges = set()
            for u, v in self.network.graph.edges():
                old_edges.add(tuple(sorted((u, v))))
                
            self.network.update_links()
            
            new_edges = set()
            for u, v in self.network.graph.edges():
                new_edges.add(tuple(sorted((u, v))))
            
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
            for i, (src, dst) in enumerate(self.flows):
                while t >= self.next_packet_times[i]:
                    pkt = Packet(src=src, dst=dst, created_at=self.next_packet_times[i], size=self.config.packet_size)
                    pkt.queued_at = self.next_packet_times[i]
                    self.network.nodes[src].queue.append(pkt)
                    if len(self.network.nodes[src].queue) >= int(0.8 * self.config.max_queue_capacity):
                        self.metrics.on_congestion_event()
                    self.metrics.on_send(pkt, self.next_packet_times[i], flow_id=i)
                    self.next_packet_times[i] += self.rng.exponential(1.0 / self.config.packet_rate)
            
            # 6. BUG 2: Partition Detection Fix
            if self.time >= self.WARMUP_PERIOD:
                alive_flows = [
                    (s, d) for s, d in self.flows
                    if self.network.nodes[s].energy > 0
                    and self.network.nodes[d].energy > 0
                ]
                if alive_flows:
                    reachable_count = sum(
                        1 for s, d in alive_flows
                        if nx.has_path(self.network.graph, s, d)
                    )
                    ratio = reachable_count / len(alive_flows)
                    now_partitioned = ratio < 0.5
                    if now_partitioned and not self._in_partition:
                        logger.warning(
                            f"NETWORK PARTITION DETECTED at time "
                            f"{self.time:.1f}s "
                            f"({reachable_count}/{len(alive_flows)} "
                            f"flows reachable)"
                        )
                        self._in_partition = True
                    elif not now_partitioned and self._in_partition:
                        logger.info(
                            f"NETWORK PARTITION RESOLVED at time "
                            f"{self.time:.1f}s"
                        )
                        self._in_partition = False
                    
            # 7. Packet forwarding
            self._forward_all_packets(t)
            
            # 8. Node state updates
            for node in self.network.nodes.values():
                node.update_queue_history()
                
            # 9. Snapshots and Callbacks
            if step % max(1, int(self.config.snapshot_interval / self.config.time_step)) == 0:
                snap = self.metrics.snapshot(t, window=self.config.snapshot_interval)
                snap.protocol_name = self.protocol.name
                snap.config_seed = self.config.seed
                snap.num_nodes = self.config.num_nodes
                snap.max_speed = self.config.max_speed
                if self.on_snapshot_cb:
                    self.on_snapshot_cb(t, snap)
            
            if self.on_step_cb:
                self.on_step_cb(t)
                
            if real_time:
                time.sleep(self.config.time_step * 0.1) # Throttle for real-time visualization

        return self.metrics

    def _forward_all_packets(self, t: float):
        """Simulates packet transmission across the network."""
        next_step_queues = {node_id: [] for node_id in self.network.nodes}
        active_nodes_this_step = set()
        
        for node_id, node in self.network.nodes.items():
            if not node.queue:
                continue
                
            if node.energy <= 0:
                # BUG 2: Energy death logging Fix
                if node.id not in self._dead_nodes:
                    logger.warning(
                        f"Node {node.id} battery dead at t={self.time:.1f}s"
                    )
                    self._dead_nodes.add(node.id)
                
                # Node is dead, packets are lost
                for pkt in node.queue:
                    self.metrics.on_drop(pkt, t, "Node Dead")
                    if hasattr(self.protocol, 'on_packet_dropped'):
                        self.protocol.on_packet_dropped(pkt)
                node.queue = []
                continue

            packets_to_process = node.queue[:]
            node.queue = []
            
            for pkt in packets_to_process:
                # Route discovery timeout drop
                if pkt.queued_at and (t - pkt.queued_at) > 5.0:
                    pkt.drop_reason = 'route_discovery_timeout'
                    self.metrics.on_drop(pkt, t, reason='route_discovery_timeout')
                    if hasattr(self.protocol, 'on_packet_dropped'):
                        self.protocol.on_packet_dropped(pkt)
                    continue

                if pkt.dst == node_id:
                    # BUG 3 Fix A: on_packet_delivered
                    self.metrics.on_deliver(pkt, t, flow_id=getattr(pkt, 'flow_id', -1))
                    if hasattr(self.protocol, 'on_packet_delivered'):
                        self.protocol.on_packet_delivered(pkt, t)
                    continue
                    
                if pkt.ttl <= 0:
                    # BUG 3 Fix A: on_packet_dropped for TTL
                    pkt.drop_reason = 'ttl_expired'
                    self.metrics.on_drop(pkt, t, reason='ttl_expired')
                    if hasattr(self.protocol, 'on_packet_dropped'):
                        self.protocol.on_packet_dropped(pkt)
                    continue
                    
                next_hop = self.protocol.get_next_hop(node_id, pkt)
                
                if next_hop != -1 and next_hop in self.network.get_neighbors(node_id):
                    # Transmit
                    pkt.hop_count += 1
                    pkt.ttl -= 1
                    pkt.route.append(node_id)
                    pkt.queued_at = t # reset queue time
                    next_step_queues[next_hop].append(pkt)
                    
                    active_nodes_this_step.add(node_id)
                    
                    energy_cost = node.energy_cost_to_forward(pkt.size)
                    node.consume_energy(energy_cost)
                    self.metrics.energy_consumed += energy_cost
                    
                    self.packet_positions.append({'source': node_id, 'target': next_hop})
                else:
                    # No route or link break
                    if next_hop == -1:
                        # Re-queue for next step (limited buffer)
                        if len(node.queue) < self.config.max_queue_capacity:
                            node.queue.append(pkt)
                        else:
                            self.metrics.on_drop(pkt, t, "Queue Overflow")
                            if hasattr(self.protocol, 'on_packet_dropped'):
                                self.protocol.on_packet_dropped(pkt)
                    else:
                        self.metrics.on_drop(pkt, t, "No Route")
                        if hasattr(self.protocol, 'on_packet_dropped'):
                            self.protocol.on_packet_dropped(pkt)

        # Merge staged packets back
        for node_id, pkts in next_step_queues.items():
            if pkts:
                node = self.network.nodes[node_id]
                for p in pkts:
                    if len(node.queue) < self.config.max_queue_capacity:
                        node.queue.append(p)
                        if len(node.queue) >= int(0.8 * self.config.max_queue_capacity):
                            self.metrics.on_congestion_event()
                    else:
                        self.metrics.on_drop(p, t, "Queue Overflow")
                        if hasattr(self.protocol, 'on_packet_dropped'):
                            self.protocol.on_packet_dropped(p)
                            
        self.metrics.record_active_nodes(active_nodes_this_step)

    def get_topology_for_dashboard(self) -> dict:
        snap = self.network.topology_snapshot()
        snap['packets'] = self.packet_positions
        return snap
