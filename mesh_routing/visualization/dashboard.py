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
        self.interactive_nodes = [] 
        self.interactive_src = None
        self.interactive_dst = None
        self.interactive_tx_range = 150.0
        self.narration = "Welcome! Place some devices and start a journey."

state = DashboardState()

ICONS = {'router': '🔴 Router', 'pc': '🖥️ PC', 'laptop': '💻 Laptop', 'access_point': '📡 AP'}
UNICODE_ICONS = {'router': '⬢', 'pc': '🖥️', 'laptop': '💻', 'access_point': '📡'}
SYMBOLS = {'router': 'hexagon', 'pc': 'square', 'laptop': 'diamond', 'access_point': 'star'}

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

def get_research_sidebar():
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
    ], id='research-sidebar-inner')

def get_interactive_sidebar():
    return html.Div([
        html.H3("Interactive Mode", style={'color': CISCO_BLUE, 'fontWeight': 'bold'}),
        html.Hr(),
        html.Label("Add Device"),
        html.Div(dcc.Dropdown(id='device-type-dropdown', options=[{'label': v, 'value': k} for k, v in ICONS.items()], value='router')),
        html.Button("Add to Canvas", id='add-device-btn', style={'width': '100%'}),
        html.Button("Clear", id='clear-canvas-btn', style={'width': '100%', 'backgroundColor': '#dc3545', 'color': 'white'}),
        html.Hr(),
        html.Label("Quick Nodes"),
        html.Div(dcc.Input(id='quick-nodes-input', type='number', min=5, max=20, value=10)),
        html.Button("Auto-Place", id='auto-place-btn', style={'width': '100%'}),
        html.Hr(),
        html.Label("Range (m)"),
        html.Div(dcc.Slider(id='tx-range-slider', min=50, max=300, step=10, value=150)),
        html.Hr(),
        html.Label("Source"), html.Div(dcc.Dropdown(id='source-dropdown', options=[])),
        html.Label("Destination"), html.Div(dcc.Dropdown(id='destination-dropdown', options=[])),
        html.Hr(),
        html.Div(dcc.RadioItems(id='interactive-protocol-radio', options=[{'label': 'CPQR', 'value': 'CPQR'}, {'label': 'AODV', 'value': 'AODV'}], value='CPQR')),
        html.Br(),
        html.Button("▶ START JOURNEY", id='start-journey-btn', style={'width': '100%', 'backgroundColor': CISCO_BLUE, 'color': 'white'})
    ], id='interactive-sidebar-inner')

app = dash.Dash(__name__, external_stylesheets=['https://codepen.io/chriddyp/pen/bWLwgP.css'], suppress_callback_exceptions=True)
app.index_string = '''<!DOCTYPE html><html><head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}<style>._dash-loading, .dash-spinner { display: none !important; }</style></head><body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>'''

app.layout = html.Div([
    html.Div(id='research-sidebar-container', style=SIDEBAR_STYLE, children=get_research_sidebar()),
    html.Div(id='interactive-sidebar-container', style={**SIDEBAR_STYLE, 'display': 'none'}, children=get_interactive_sidebar()),
    html.Div([
        dcc.Tabs(id='main-tabs', value='research', children=[dcc.Tab(label='📊 Research Mode', value='research'), dcc.Tab(label='🖥️ Interactive Mode', value='interactive')]),
        html.Div(id='research-content', style={'marginTop': '20px'}, children=[
            html.H2("Research Dashboard", style={'color': CISCO_BLUE}),
            html.Div(id='status-banner'), html.Div(id='protocol-info'),
            html.Div([
                html.Div([dcc.Graph(id='topology-graph', figure=EMPTY_FIG, style={'height': '600px'}), html.Div(id='animation-status')], className="eight columns"),
                html.Div([dcc.Graph(id='metrics-chart', figure=EMPTY_FIG, style={'height': '300px'}), html.Div(id='early-pdr-display'), dcc.Graph(id='throughput-chart', figure=EMPTY_FIG, style={'height': '300px'}), dcc.Graph(id='reward-chart', figure=EMPTY_FIG, style={'height': '300px'})], className="four columns")
            ], className="row")
        ]),
        html.Div(id='interactive-content', style={'marginTop': '20px', 'display': 'none'}, children=[
            html.H2("Interactive Mode", style={'color': CISCO_BLUE}),
            html.Div([
                html.Div([dcc.Graph(id='interactive-canvas', figure=EMPTY_FIG, style={'height': '600px'}), html.Div(id='interactive-animation-status')], className="nine columns"),
                html.Div([html.H5("Legend"), html.Div("🟢 Source | 🔴 Dest | 🔵 Relay")], className="three columns")
            ], className="row"),
            html.Div(id='narration-panel', style={'padding': '15px', 'backgroundColor': '#f8f9fa'})
        ])
    ], style=CONTENT_STYLE),
    dcc.Interval(id='interval-component', interval=500),
    dcc.Interval(id='interval-component-slow', interval=2000),
    dcc.Interval(id='animation-interval', interval=300)
])

@app.callback([Output('research-content', 'style'), Output('interactive-content', 'style'), Output('research-sidebar-container', 'style'), Output('interactive-sidebar-container', 'style')], [Input('main-tabs', 'value')])
def toggle_tabs(tab):
    logger.warning(f"DEBUG: toggle_tabs triggered: {tab}")
    res_v = {'marginTop': '20px'} if tab == 'research' else {'display': 'none'}
    int_v = {'marginTop': '20px'} if tab == 'interactive' else {'display': 'none'}
    res_s = SIDEBAR_STYLE if tab == 'research' else {**SIDEBAR_STYLE, 'display': 'none'}
    int_s = SIDEBAR_STYLE if tab == 'interactive' else {**SIDEBAR_STYLE, 'display': 'none'}
    return res_v, int_v, res_s, int_s

@app.callback([Output('interactive-canvas', 'figure'), Output('source-dropdown', 'options'), Output('destination-dropdown', 'options'), Output('narration-panel', 'children')], [Input('add-device-btn', 'n_clicks'), Input('clear-canvas-btn', 'n_clicks'), Input('auto-place-btn', 'n_clicks'), Input('source-dropdown', 'value'), Input('destination-dropdown', 'value'), Input('tx-range-slider', 'value'), Input('animation-interval', 'n_intervals')], [State('device-type-dropdown', 'value'), State('quick-nodes-input', 'value'), State('main-tabs', 'value')])
def update_interactive_canvas(add_n, clear_n, auto_n, src, dst, tx_range, anim_n, device_type, quick_n, active_tab):
    if active_tab != 'interactive': return [dash.no_update]*4
    ctx = dash.callback_context
    trigger = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else ""
    with state.lock:
        if trigger == 'animation-interval' and not state.current_animating_path: return [dash.no_update]*4
        if trigger == 'clear-canvas-btn': state.interactive_nodes, state.interactive_src, state.interactive_dst, state.narration = [], None, None, "Cleared."
        elif trigger == 'add-device-btn' and len(state.interactive_nodes) < 20: state.interactive_nodes.append({'id': len(state.interactive_nodes), 'x': np.random.uniform(50, 450), 'y': np.random.uniform(50, 450), 'type': device_type})
        elif trigger == 'auto-place-btn':
            state.interactive_nodes = []
            for i in range(quick_n): state.interactive_nodes.append({'id': i, 'x': 250 + 150*np.cos(2*np.pi*i/quick_n), 'y': 250 + 150*np.sin(2*np.pi*i/quick_n), 'type': 'router'})
        fig = go.Figure()
        # Draw all potential links
        for i, n1 in enumerate(state.interactive_nodes):
            for j, n2 in enumerate(state.interactive_nodes):
                if i >= j: continue
                if np.sqrt((n1['x']-n2['x'])**2 + (n1['y']-n2['y'])**2) <= tx_range:
                    fig.add_trace(go.Scatter(x=[n1['x'], n2['x'], None], y=[n1['y'], n2['y'], None], mode='lines', line=dict(color=GRID_COLOR, width=1), opacity=0.3, hoverinfo='none'))
        
        # Draw Packet if animating
        if state.current_animating_path and state.animating_hop_idx < len(state.current_animating_path) - 1:
            u_id = state.current_animating_path[state.animating_hop_idx]
            v_id = state.current_animating_path[state.animating_hop_idx + 1]
            u = next(n for n in state.interactive_nodes if n['id'] == u_id)
            v = next(n for n in state.interactive_nodes if n['id'] == v_id)
            # Intermediate position for packet
            fig.add_trace(go.Scatter(x=[(u['x']+v['x'])/2], y=[(u['y']+v['y'])/2], mode='markers', marker=dict(size=15, color='orange', symbol='circle'), name='Traveling Packet'))

        # Draw Nodes
        for node in state.interactive_nodes:
            c = CISCO_BLUE
            if str(node['id']) == str(src): c = 'green'
            elif str(node['id']) == str(dst): c = 'red'
            
            # Highlight relay nodes in the path
            if state.current_animating_path and node['id'] in state.current_animating_path:
                idx = state.current_animating_path.index(node['id'])
                if idx == state.animating_hop_idx: c = 'yellow' # Current focus
                elif idx < state.animating_hop_idx: c = '#a0d1ff' # Visited

            fig.add_trace(go.Scatter(x=[node['x']], y=[node['y']], mode='markers+text', marker=dict(size=25, color=c, symbol=SYMBOLS.get(node['type'], 'circle'), line=dict(width=2, color='white')), text=[f"N{node['id']}"], textposition="top center"))
            
        fig.update_layout(xaxis=dict(range=[0, 500], showgrid=True, gridcolor=GRID_COLOR), yaxis=dict(range=[0, 500], showgrid=True, gridcolor=GRID_COLOR), plot_bgcolor='white', margin=dict(b=0,l=0,r=0,t=0), uirevision='const', showlegend=False)
        opts = [{'label': f"Node {n['id']}", 'value': str(n['id'])} for n in state.interactive_nodes]
        return fig, opts, opts, state.narration

@app.callback(Output('interactive-animation-status', 'children'), [Input('start-journey-btn', 'n_clicks')], [State('source-dropdown', 'value'), State('destination-dropdown', 'value'), State('interactive-protocol-radio', 'value'), State('tx-range-slider', 'value')])
def start_journey(n, src, dst, proto, tx):
    logger.warning(f"DEBUG: start_journey triggered (clicks: {n})")
    if not n or not src or not dst: return ""
    with state.lock:
        config = SimConfig(num_nodes=len(state.interactive_nodes), tx_range=tx)
        net = WirelessNetwork(config)
        for node in state.interactive_nodes: net.add_node(Node(node['id'], node['x'], node['y'], config))
        net.update_links()
        if not net.is_connected(int(src), int(dst)): return "No path!"
        p_map = {'AODV': AODV, 'OLSR': OLSR, 'CPQR': CPQR}
        engine = SimulationEngine(p_map[proto], config)
        engine.network, engine.protocol = net, p_map[proto](net, config)
        path, curr, pkt = [int(src)], int(src), Packet(int(src), int(dst), 0.0)
        while curr != int(dst) and len(path) < 20:
            nxt = engine.protocol.get_next_hop(curr, pkt)
            if nxt == -1: break
            path.append(nxt); curr = nxt
        state.current_animating_path, state.animating_hop_idx = path, 0
        return f"Path: {' -> '.join(map(str, path))}"

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

@app.callback([Output('topology-graph', 'figure'), Output('metrics-chart', 'figure'), Output('early-pdr-display', 'children'), Output('throughput-chart', 'figure'), Output('reward-chart', 'figure'), Output('q-stats-display', 'children'), Output('status-banner', 'children'), Output('q-table-panel', 'style')], [Input('interval-component', 'n_intervals')], [State('main-tabs', 'value')])
def update_res(n, tab):
    if tab != 'research': return [dash.no_update]*8
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
        topo.add_trace(go.Scatter(x=node_x, y=node_y, mode='markers+text', marker=dict(size=15, color=node_c), text=[str(n['id']) for n in nodes]))
        topo.update_layout(xaxis=dict(range=[0, 500], showgrid=False, zeroline=False), yaxis=dict(range=[0, 500], showgrid=False, zeroline=False), margin=dict(b=0,l=0,r=0,t=0), uirevision='const', showlegend=False)
        hist = state.metrics_history
        pdr_f = go.Figure(data=[go.Scatter(x=[m['time'] for m in hist], y=[m['pdr'] for m in hist], fill='tozeroy', line=dict(color=CISCO_BLUE))], layout=go.Layout(title="Packet Delivery Ratio", yaxis=dict(range=[0, 1.1]), uirevision='const', margin=dict(l=40, r=20, t=40, b=40)))
        tput_f = go.Figure(data=[go.Scatter(x=[m['time'] for m in hist], y=[m['throughput_bps']/1000 for m in hist], fill='tozeroy', line=dict(color='green'))], layout=go.Layout(title="Throughput (kbps)", uirevision='const', margin=dict(l=40, r=20, t=40, b=40)))
        
        # Reward Chart logic
        reward_f = EMPTY_FIG
        if state.protocol_name == 'CPQR':
            comps = state.reward_components
            labels = ['Delay', 'Congestion', 'Link', 'Energy']
            values = [comps.get(l.lower(), 0) for l in labels]
            logger.warning(f"DEBUG: Reward components: {comps}, values: {values}")
            if sum(values) > 0:
                reward_f = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.4, marker=dict(colors=['#007bff', '#ffc107', '#dc3545', '#28a745']))])
                reward_f.update_layout(title="Reward Breakdown", margin=dict(l=10, r=10, t=40, b=10), showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            else:
                logger.warning("DEBUG: sum(values) is 0, keeping EMPTY_FIG")

        status = "● LIVE" if not state.finished else "✓ DONE"
        q_style = {'display': 'block'} if state.protocol_name == 'CPQR' else {'display': 'none'}
        return topo, pdr_f, f"Early: {state.early_pdr:.1%}", tput_f, reward_f, f"Avg Q: {state.q_stats['mean']:.2f}", status, q_style

def run_simulation(proto, n, speed, load, dur):
    logger.warning(f"DEBUG: run_simulation started: {proto}")
    p_map = {'AODV': AODV, 'OLSR': OLSR, 'CPQR': CPQR}
    config = SimConfig(num_nodes=n, max_speed=speed, packet_rate=load, duration=dur)
    engine = SimulationEngine(p_map[proto], config, RandomWaypointMobility)
    engine.on_snapshot_cb = lambda t, s: update_metrics(engine)
    engine.on_step_cb = lambda t: update_topology(engine)
    with state.lock: state.finished, state.metrics_history, state.topology, state.current_time, state.config = False, [], {'nodes': [], 'edges': []}, 0.0, config
    engine.run(real_time=True)
    with state.lock: state.finished = True
    logger.warning(f"DEBUG: run_simulation finished")

@app.callback(Output('protocol-info', 'children'), Input('restart-btn', 'n_clicks'), [State('protocol-dropdown', 'value'), State('nodes-slider', 'value'), State('speed-slider', 'value'), State('load-slider', 'value'), State('duration-input', 'value')])
def restart(n, proto, nodes, speed, load, dur):
    logger.warning(f"DEBUG: restart clicked (n_clicks: {n})")
    if n is None: return "Ready."
    threading.Thread(target=run_simulation, args=(proto, nodes, speed, load, dur), daemon=True).start()
    return f"Starting {proto}..."

def run_dashboard(port=8050): app.run(debug=False, port=port)
if __name__ == '__main__': run_dashboard()
