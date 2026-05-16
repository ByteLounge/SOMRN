from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time
import logging
from typing import Dict, List, Optional
import numpy as np

from simulation.engine import SimulationEngine
from config import SimConfig, ScenarioPresets
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR
from protocols.q_routing import QRouting
from protocols.pqr import PQR
from protocols.drl_routing import DRLRouting
from core.mobility import RandomWaypointMobility, StaticMobility
from visualization.narrator import Narrator
from visualization.chaos import ChaosController

app = Flask(__name__)
CORS(app) # Enable CORS for React frontend

# --- State Management ---
class GlobalState:
    def __init__(self):
        self.lock = threading.Lock()
        self.engine = None
        self.stop_event = threading.Event()
        self.thread = None
        self.narrator = None
        self.chaos = None
        self.last_snapshot = None
        self.events = []
        self.running = False
        self.scenario_meta = None
        self.current_params = {}

state = GlobalState()

def run_simulation_thread(engine, stop_event):
    last_delivered = 0
    last_dropped = 0
    last_breaks = 0
    
    try:
        def on_step(t):
            nonlocal last_delivered, last_dropped, last_breaks
            if stop_event.is_set():
                return
            
            # Narrative logic
            if state.narrator:
                curr_delivered = len(engine.metrics.delivered)
                if curr_delivered > last_delivered:
                    new_pkts = engine.metrics.delivered[last_delivered:]
                    for _, p in new_pkts:
                        state.narrator.on_packet_delivered(p.hop_count, p.delivered_at - p.created_at)
                    last_delivered = curr_delivered
                
                curr_dropped = len(engine.metrics.dropped)
                if curr_dropped > last_dropped:
                    new_pkts = engine.metrics.dropped[last_dropped:]
                    for _, p in new_pkts:
                        state.narrator.on_packet_dropped(p.drop_reason)
                    last_dropped = curr_dropped
                    
                if engine.metrics.route_breaks > last_breaks:
                    state.narrator.on_link_break(0, 0)
                    last_breaks = engine.metrics.route_breaks

        def on_snapshot(t, snap):
            state.last_snapshot = snap

        engine.on_step_cb = on_step
        engine.on_snapshot_cb = on_snapshot
        engine.run(real_time=True)
        
    except Exception as e:
        print(f"Error in simulation thread: {e}")
    finally:
        state.running = False

# --- API Endpoints ---

@app.route('/api/status', methods=['GET'])
def get_status():
    return jsonify({
        "running": state.running,
        "params": state.current_params
    })

@app.route('/api/start', methods=['POST'])
def start_sim():
    data = request.json
    protocol_name = data.get('protocol', 'cpqr').lower().replace('-', '_')
    scenario = data.get('scenario', 'default')
    num_nodes = data.get('nodes', 30)
    num_flows = data.get('flows', 5)
    mode = data.get('mode', 'expert')

    # Stop existing
    state.stop_event.set()
    if state.thread:
        state.thread.join(timeout=0.5)
    
    state.stop_event.clear()
    
    # Configure
    presets = ScenarioPresets.get_all()
    if scenario != 'default' and scenario in presets:
        cfg, meta = presets[scenario]
        state.scenario_meta = meta
    else:
        cfg = SimConfig()
        state.scenario_meta = {
            'name': 'Generic Field Test',
            'tagline': 'Standard network testing conditions.',
            'thumbnail': '📶',
            'context_color': '#3b82f6'
        }
    
    cfg.num_nodes = num_nodes
    cfg.num_flows = num_flows
    
    m_cls = RandomWaypointMobility
    if mode in ['beginner', 'intermediate', 'story']:
        cfg.trace_mode = True
        cfg.packet_rate = 0.5
        cfg.max_speed = 0.0
        m_cls = StaticMobility

    p_map = {
        'aodv': AODV, 'olsr': OLSR, 'cpqr': CPQR,
        'q_routing': QRouting, 'pqr': PQR, 'drl': DRLRouting
    }
    p_cls = p_map.get(protocol_name, CPQR)
    
    state.engine = SimulationEngine(p_cls, cfg, m_cls)
    state.narrator = Narrator(state.scenario_meta)
    state.chaos = ChaosController(state.engine, state.narrator)
    state.current_params = data
    state.running = True
    
    state.thread = threading.Thread(target=run_simulation_thread, args=(state.engine, state.stop_event), daemon=True)
    state.thread.start()
    
    return jsonify({"status": "started"})

@app.route('/api/stop', methods=['POST'])
def stop_sim():
    state.stop_event.set()
    state.running = False
    return jsonify({"status": "stopped"})

@app.route('/api/state', methods=['GET'])
def get_state():
    if not state.engine:
        return jsonify({"error": "No simulation active"}), 400
    
    topo = state.engine.get_topology_for_dashboard()
    
    # Format metrics
    metrics = {
        "delivered": len(state.engine.metrics.delivered),
        "dropped": len(state.engine.metrics.dropped),
        "total": state.engine.metrics.total_sent,
        "delay": state.engine.metrics.avg_delay,
        "breaks": state.engine.metrics.route_breaks,
        "predictions": getattr(state.engine.metrics, 'proactive_reroutes', 0),
        "pdr": state.engine.metrics.pdr
    }
    
    # Get narrative feed
    feed = []
    if state.narrator:
        feed = state.narrator.get_feed()

    return jsonify({
        "topology": topo,
        "metrics": metrics,
        "events": feed,
        "time": state.engine.time,
        "running": state.running
    })

@app.route('/api/chaos', methods=['POST'])
def trigger_chaos():
    if state.chaos:
        state.chaos.trigger()
        return jsonify({"status": "triggered"})
    return jsonify({"error": "No simulation active"}), 400

if __name__ == '__main__':
    app.run(port=5000, debug=False)
