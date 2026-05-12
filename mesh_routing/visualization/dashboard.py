import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import threading
import time
import pandas as pd
from datetime import datetime
import os
from typing import Dict, List, Optional
import numpy as np
import uuid
import logging

# Configure logging to be visible in terminal
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("dashboard")

from simulation.engine import SimulationEngine
from config import SimConfig, ScenarioPresets
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR
from core.mobility import RandomWaypointMobility
from core.node import Node
from core.packet import Packet
from core.network import WirelessNetwork

class DashboardState:
    def __init__(self):
        self.lock = threading.Lock()
        self.topology = {'nodes': [], 'edges': [], 'packets': []}
        self.metrics_history: List[dict] = []
        self.current_time = 0.0
        self.protocol_name = ""
        self.q_stats = {'mean': 0, 'max': 0, 'min': 0}
        self.epsilon = 0.0
        self.proactive_reroutes = 0
        self.q_guided_pct = 0.0
        self.reward_components = {'delay': 0.0, 'congestion': 0.0, 'link': 0.0, 'energy': 0.0, 'count': 0}
        self.congestion_events = 0
        self.early_pdr = 0.0
        self.finished = False
        self.config = SimConfig()
        self.completed_routes: List[dict] = []
        self.current_animating_path: List[int] = []
        self.animating_hop_idx = 0

state = DashboardState()

CISCO_BLUE = "#005a9e"
GRID_COLOR = "#e5e5e5"
SIDEBAR_STYLE = {"position": "fixed", "top": 0, "left": 0, "bottom": 0, "width": "320px", "padding": "20px", "background-color": "#f8f9fa", "border-right": "1px solid #dee2e6", "overflow-y": "auto", "z-index": 1000}
CONTENT_STYLE = {"margin-left": "340px", "padding": "20px"}

EMPTY_FIG = go.Figure(layout=go.Layout(xaxis=dict(visible=True, range=[0, 500], showgrid=True, gridcolor=GRID_COLOR), yaxis=dict(visible=True, range=[0, 500], showgrid=True, gridcolor=GRID_COLOR), plot_bgcolor='white', paper_bgcolor='white', margin=dict(l=40, r=20, t=40, b=40), uirevision='constant'))

def update_topology(engine):
    with state.lock:
        state.topology = engine.get_topology_for_dashboard()
        state.current_time = engine.time
        new_routes = engine.get_last_packet_routes()
        if new_routes:
            state.completed_routes.extend(new_routes)
            if len(state.completed_routes) > 10: state.completed_routes = state.completed_routes[-10:]
        if engine.protocol and hasattr(engine.protocol, 'get_qtable_stats'):
             state.q_stats = engine.protocol.get_qtable_stats()
             state.epsilon = getattr(engine.protocol, 'epsilon', 0.0)
             state.proactive_reroutes = getattr(engine.protocol, 'proactive_reroutes_count', 0)
             q_conf = getattr(engine.protocol, 'q_confidence', {})
             nodes_in_q_mode = sum(1 for conf in q_conf.values() if any(c >= engine.config.min_explore_count for c in conf.values()))
             total_active_nodes = len(q_conf)
             state.q_guided_pct = (nodes_in_q_mode / total_active_nodes * 100) if total_active_nodes > 0 else 0.0
             state.reward_components = getattr(engine.protocol, 'reward_components', {}).copy()

def update_metrics(engine):
    with state.lock:
        state.metrics_history = [vars(s) for s in engine.metrics.snapshots]
        state.protocol_name = engine.protocol.name
        state.congestion_events = getattr(engine.metrics, 'congestion_events', 0)
        state.early_pdr = getattr(engine.metrics, 'early_pdr', 0.0)

def get_sidebar():
    return html.Div([
        html.H3("SOMRN DASHBOARD", style={'color': CISCO_BLUE, 'fontWeight': 'bold'}),
        html.Hr(),
        html.Label("Protocol"),
        html.Div(dcc.Dropdown(id='protocol-dropdown', options=[{'label': 'AODV', 'value': 'AODV'}, {'label': 'OLSR', 'value': 'OLSR'}, {'label': 'CPQR', 'value': 'CPQR'}], value='CPQR', clearable=False)),
        html.Br(),
        html.Label("Number of Nodes"),
        html.Div(dcc.Slider(id='nodes-slider', min=10, max=100, step=5, value=30)),
        html.Label("Max Speed (m/s)"),
        html.Div(dcc.Slider(id='speed-slider', min=0, max=30, step=1, value=5)),
        html.Label("Packet Rate (pkts/s)"),
        html.Div(dcc.Slider(id='load-slider', min=0.5, max=20, step=0.5, value=2)),
        html.Label("Duration (s)"),
        html.Div(dcc.Input(id='duration-input', type='number', value=300)),
        html.Br(),
        html.Button("START SIMULATION", id='restart-btn', style={'width': '100%', 'backgroundColor': CISCO_BLUE, 'color': 'white'}),
        html.Hr(),
        html.Div(id='q-table-panel', children=[html.H6("AI Status"), html.Div(id='q-stats-display'), html.Div(id='cpqr-intelligence-status')])
    ], id='sidebar-inner')

app = dash.Dash(__name__, external_stylesheets=['https://codepen.io/chriddyp/pen/bWLwgP.css'], suppress_callback_exceptions=True)
app.index_string = '''<!DOCTYPE html><html><head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}<style>._dash-loading, .dash-spinner { display: none !important; }</style></head><body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>'''

app.layout = html.Div([
    html.Div(id='sidebar-container', style=SIDEBAR_STYLE, children=get_sidebar()),
    html.Div([
        html.Div(id='research-content', style={'marginTop': '20px'}, children=[
            html.H2("Research Dashboard", style={'color': CISCO_BLUE}),
            html.Div(id='status-banner'), html.Div(id='protocol-info'),
            html.Div([
                html.Div([dcc.Graph(id='topology-graph', figure=EMPTY_FIG, style={'height': '600px'}), html.Div(id='animation-status')], className="eight columns"),
                html.Div([dcc.Graph(id='metrics-chart', figure=EMPTY_FIG, style={'height': '300px'}), html.Div(id='early-pdr-display'), dcc.Graph(id='throughput-chart', figure=EMPTY_FIG, style={'height': '300px'}), dcc.Graph(id='reward-chart', figure=EMPTY_FIG, style={'height': '300px'})], className="four columns")
            ], className="row")
        ])
    ], style=CONTENT_STYLE),
    dcc.Interval(id='interval-component', interval=500),
    dcc.Interval(id='interval-component-slow', interval=2000),
    dcc.Interval(id='animation-interval', interval=300)
])

@app.callback([Output('animation-status', 'children')], [Input('animation-interval', 'n_intervals')])
def anim_step(n):
    with state.lock:
        if not state.current_animating_path:
            if state.completed_routes:
                r = state.completed_routes.pop(0)
                state.current_animating_path, state.animating_hop_idx = r['path'], 0
            return [dash.no_update]
        state.animating_hop_idx += 1
        if state.animating_hop_idx >= len(state.current_animating_path):
            state.current_animating_path = []
            return ["Done"]
        return [f"At {state.current_animating_path[state.animating_hop_idx]}"]

@app.callback([Output('topology-graph', 'figure'), Output('metrics-chart', 'figure'), Output('early-pdr-display', 'children'), Output('throughput-chart', 'figure'), Output('reward-chart', 'figure'), Output('q-stats-display', 'children'), Output('status-banner', 'children'), Output('q-table-panel', 'style')], [Input('interval-component', 'n_intervals')])
def update_res(n):
    with state.lock:
        nodes = state.topology.get('nodes', [])
        if not nodes: return EMPTY_FIG, EMPTY_FIG, "N/A", EMPTY_FIG, EMPTY_FIG, "N/A", "IDLE", {'display': 'none'}
        topo = go.Figure()
        for e in state.topology.get('edges', []):
            s, t = next(n for n in nodes if n['id']==e['source']), next(n for n in nodes if n['id']==e['target'])
            topo.add_trace(go.Scatter(x=[s['x'], t['x'], None], y=[s['y'], t['y'], None], mode='lines', line=dict(color='green'), opacity=0.3))
        node_x, node_y, node_c = [n['x'] for n in nodes], [n['y'] for n in nodes], [CISCO_BLUE for n in nodes]
        if state.current_animating_path and state.animating_hop_idx < len(state.current_animating_path):
            curr_id = state.current_animating_path[state.animating_hop_idx]
            for i, n_info in enumerate(nodes):
                if n_info['id'] == curr_id: node_c[i] = 'yellow'
        # 2. Draw Nodes
        node_x, node_y, node_c = [n['x'] for n in nodes], [n['y'] for n in nodes], [CISCO_BLUE for n in nodes]
        topo.add_trace(go.Scatter(x=node_x, y=node_y, mode='markers+text', marker=dict(size=14, color=node_c, line=dict(width=1, color='white')), text=[str(n['id']) for n in nodes], textposition="top center", hoverinfo='text'))
        
        # 3. Draw Active Packets (Moving Dots)
        packets = state.topology.get('packets', [])
        if packets:
            px, py = [], []
            for p in packets:
                s_node = next((n for n in nodes if n['id'] == p['source']), None)
                t_node = next((n for n in nodes if n['id'] == p['target']), None)
                if s_node and t_node:
                    px.append((s_node['x'] + t_node['x'])/2)
                    py.append((s_node['y'] + t_node['y'])/2)
            topo.add_trace(go.Scatter(x=px, y=py, mode='markers', marker=dict(size=10, color='orange', symbol='circle'), name='Packets', hoverinfo='none'))

        topo.update_layout(xaxis=dict(range=[0, 500], showgrid=False, zeroline=False), yaxis=dict(range=[0, 500], showgrid=False, zeroline=False), margin=dict(b=0,l=0,r=0,t=0), uirevision='const', showlegend=False)
        hist = state.metrics_history
        pdr_f = go.Figure(data=[go.Scatter(x=[m['time'] for m in hist], y=[m['pdr'] for m in hist], fill='tozeroy', line=dict(color=CISCO_BLUE))], layout=go.Layout(title="Packet Delivery Ratio", yaxis=dict(range=[0, 1.1]), uirevision='const', margin=dict(l=40, r=20, t=40, b=40)))
        tput_f = go.Figure(data=[go.Scatter(x=[m['time'] for m in hist], y=[m['throughput_bps']/1000 for m in hist], fill='tozeroy', line=dict(color='green'))], layout=go.Layout(title="Throughput (kbps)", uirevision='const', margin=dict(l=40, r=20, t=40, b=40)))
        
        # Reward Chart logic
        reward_f = EMPTY_FIG
        if state.protocol_name.upper() == 'CPQR':
            comps = state.reward_components
            labels = ['Delay', 'Congestion', 'Link', 'Energy']
            values = [comps.get(l.lower(), 0.0) for l in labels]
            if sum(values) > 0:
                reward_f = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4, marker=dict(colors=['#007bff', '#ffc107', '#dc3545', '#28a745']))])
                reward_f.update_layout(title="Reward Breakdown", margin=dict(l=10, r=10, t=40, b=10), showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            else:
                logger.warning(f"Reward values sum to zero: {comps}")

        status = "● LIVE" if not state.finished else "✓ DONE"
        q_style = {'display': 'block'} if state.protocol_name.upper() == 'CPQR' else {'display': 'none'}
        return topo, pdr_f, f"Early: {state.early_pdr:.1%}", tput_f, reward_f, f"Avg Q: {state.q_stats['mean']:.2f}", status, q_style

def run_simulation(proto, n, speed, load, dur):
    p_map = {'AODV': AODV, 'OLSR': OLSR, 'CPQR': CPQR}
    config = SimConfig(num_nodes=n, max_speed=speed, packet_rate=load, duration=dur)
    engine = SimulationEngine(p_map[proto], config, RandomWaypointMobility)
    engine.on_snapshot_cb = lambda t, s: update_metrics(engine)
    engine.on_step_cb = lambda t: update_topology(engine)
    with state.lock: 
        state.finished, state.metrics_history, state.topology, state.current_time, state.config = False, [], {'nodes': [], 'edges': []}, 0.0, config
        state.protocol_name = proto
        state.reward_components = {'delay': 0.0, 'congestion': 0.0, 'link': 0.0, 'energy': 0.0, 'count': 0}
    engine.run(real_time=True)
    update_topology(engine)
    update_metrics(engine)
    with state.lock: state.finished = True

@app.callback(Output('protocol-info', 'children'), Input('restart-btn', 'n_clicks'), [State('protocol-dropdown', 'value'), State('nodes-slider', 'value'), State('speed-slider', 'value'), State('load-slider', 'value'), State('duration-input', 'value')])
def restart(n, proto, nodes, speed, load, dur):
    if n is None: return "Ready."
    threading.Thread(target=run_simulation, args=(proto, nodes, speed, load, dur), daemon=True).start()
    return f"Starting {proto}..."

def run_dashboard(port=8050): app.run(debug=False, port=port)
if __name__ == '__main__': run_dashboard()
