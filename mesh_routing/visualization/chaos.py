# visualization/chaos.py

import logging
import random

logger = logging.getLogger('mesh_routing.chaos')

class ChaosController:
    """
    Applies network stress conditions to a running simulation engine.
    Called when the user clicks the "Trigger network stress" button.
    
    Effects:
    - Doubles the packet rate on all flows
    - Maximises node speed
    - Kills two random non-source, non-destination nodes (sets energy=0)
    """

    def __init__(self, engine, narrator=None):
        self.engine = engine
        self.narrator = narrator
        self.triggered = False

    def trigger(self):
        if self.triggered:
            return {'status': 'already_triggered'}

        self.triggered = True
        cfg = self.engine.config

        # Double packet rate
        original_rate = cfg.packet_rate
        cfg.packet_rate = min(cfg.packet_rate * 2, 20.0)

        # Max out speed — update mobility model parameters
        cfg.max_speed = cfg.max_speed * 2.0
        cfg.min_speed = cfg.min_speed * 1.5

        # Kill two random non-flow-endpoint nodes
        flow_nodes = set()
        for src, dst in self.engine.flows:
            flow_nodes.add(src)
            flow_nodes.add(dst)

        candidates = [
            nid for nid in self.engine.network.nodes
            if nid not in flow_nodes
        ]
        killed = []
        kill_count = min(2, len(candidates))
        chosen = random.sample(candidates, kill_count)
        for nid in chosen:
            self.engine.network.nodes[nid].energy = 0.0
            killed.append(nid)
            logger.warning(f"ChaosController: killed node {nid}")

        if self.narrator:
            self.narrator.on_chaos_triggered()

        return {
            'status': 'triggered',
            'killed_nodes': killed,
            'new_packet_rate': cfg.packet_rate,
            'new_max_speed': cfg.max_speed,
            'original_packet_rate': original_rate,
        }

    def reset(self):
        self.triggered = False
