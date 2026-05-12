import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import threading
import time
import logging
from typing import Dict, List, Optional
import numpy as np

# Version 2.1 - Clean Research Dashboard
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("dashboard")

from simulation.engine import SimulationEngine
from config import SimConfig
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR
from core.mobility import RandomWaypointMobility

class DashboardState:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.lock = threading.Lock()
        self.topology = {'nodes': [], 'edges': [], 'packets': []}
        self.metrics_history = []
        self.current_time = 0.0
        self.protocol_name = ""
        self.q_stats = {'mean': 0, 'max': 0, 'min': 0}
        self.finished = False
        self.completed_routes = []
        self.current_animating_path = []
        self.animating_hop_idx = 0
        self.early_pdr = 0.0

state = DashboardState()

CISCO_BLUE = "#005a9e"
SIDEBAR_STYLE = {"position": "fixed", "top": 0, "left": 0, "bottom": 0, "width": "300px", "padding": "20px", "background-color": "#f8f9fa", "border-right": "1px solid #dee2e6"}
CONTENT_STYLE = {"margin-left": "320px", "padding": "20px"}
EMPTY_FIG = go.Figure(layout=go.Layout(plot_bgcolor='white', paper_bgcolor='white', margin=dict(l=40, r=20, t=40, b=40), uirevision='constant'))

def update_topology(engine):
    with state.lock:
        state.topology = engine.get_topology_for_dashboard()
        state.current_time = engine.time
        if engine.protocol and hasattr(engine.protocol, 'get_qtable_stats'):
             state.q_stats = engine.protocol.get_qtable_stats()

def update_metrics(engine):
    with state.lock:
        state.metrics_history = [vars(s) for s in engine.metrics.snapshots]
        state.protocol_name = engine.protocol.name
        state.early_pdr = getattr(engine.metrics, 'early_pdr', 0.0)

app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "SOMRN Research Console v2.1"

app.layout = html.Div([
    html.Div([
        html.H3("SOMRN v2.1", style={'color': CISCO_BLUE, 'fontWeight': 'bold'}),
        html.Hr(),
        html.Label("Protocol"),
        dcc.Dropdown(id='protocol-dropdown', options=[{'label': 'AODV', 'value': 'AODV'}, {'label': 'OLSR', 'value': 'OLSR'}, {'label': 'CPQR', 'value': 'CPQR'}], value='CPQR', clearable=False),
        html.Br(),
        html.Label("Nodes"), dcc.Slider(id='nodes-slider', min=10, max=100, step=5, value=30),
        html.Label("Speed (m/s)"), dcc.Slider(id='speed-slider', min=0, max=30, step=1, value=5),
        html.Label("Packet Rate"), dcc.Slider(id='load-slider', min=0.5, max=10, step=0.5, value=2),
        html.Br(),
        html.Button("START SIMULATION", id='restart-btn', style={'width': '100%', 'backgroundColor': CISCO_BLUE, 'color': 'white'}),
        html.Hr(),
        html.Div(id='ai-panel', children=[html.H6("Q-Learning Status"), html.Div(id='q-stats-display')])
    ], style=SIDEBAR_STYLE),
    html.Div([
        html.H2("Research Metrics", style={'color': CISCO_BLUE}),
        html.Div(id='status-banner', style={'fontWeight': 'bold'}),
        html.Div([
            html.Div([dcc.Graph(id='topo-graph', figure=EMPTY_FIG, style={'height': '600px'})], className="eight columns"),
            html.Div([
                dcc.Graph(id='pdr-chart', figure=EMPTY_FIG, style={'height': '300px'}),
                html.Div(id='early-pdr-val'),
                dcc.Graph(id='tput-chart', figure=EMPTY_FIG, style={'height': '300px'})
            ], className="four columns")
        ], className="row")
    ], style=CONTENT_STYLE),
    dcc.Interval(id='tick', interval=500)
])

@app.callback(
    [Output('topo-graph', 'figure'), Output('pdr-chart', 'figure'), Output('tput-chart', 'figure'), 
     Output('q-stats-display', 'children'), Output('status-banner', 'children'), Output('early-pdr-val', 'children')],
    [Input('tick', 'n_intervals')]
)
def refresh_ui(n):
    with state.lock:
        nodes = state.topology.get('nodes', [])
        if not nodes: return EMPTY_FIG, EMPTY_FIG, EMPTY_FIG, "N/A", "IDLE", "Early PDR: N/A"
        
        # 1. Topo
        topo = go.Figure()
        for e in state.topology.get('edges', []):
            s, t = next(n for n in nodes if n['id']==e['source']), next(n for n in nodes if n['id']==e['target'])
            topo.add_trace(go.Scatter(x=[s['x'], t['x'], None], y=[s['y'], t['y'], None], mode='lines', line=dict(color='green', width=1), opacity=0.2))
        topo.add_trace(go.Scatter(x=[n['x'] for n in nodes], y=[n['y'] for n in nodes], mode='markers+text', marker=dict(size=12, color=CISCO_BLUE), text=[str(n['id']) for n in nodes], textposition="top center"))
        topo.update_layout(xaxis=dict(range=[0, 500], showgrid=False), yaxis=dict(range=[0, 500], showgrid=False), margin=dict(l=0,r=0,b=0,t=0), uirevision='const', showlegend=False)

        # 2. Charts
        hist = state.metrics_history
        pdr = go.Figure(data=[go.Scatter(x=[m['time'] for m in hist], y=[m['pdr'] for m in hist], fill='tozeroy')], layout=go.Layout(title="PDR", yaxis=dict(range=[0, 1.1]), margin=dict(l=40,r=20,t=40,b=40), uirevision='const'))
        tput = go.Figure(data=[go.Scatter(x=[m['time'] for m in hist], y=[m['throughput_bps']/1000 for m in hist], fill='tozeroy', line=dict(color='green'))], layout=go.Layout(title="Throughput (kbps)", margin=dict(l=40,r=20,t=40,b=40), uirevision='const'))
        
        status = "● RUNNING" if not state.finished else "✓ COMPLETE"
        q_text = f"Avg Q: {state.q_stats['mean']:.2f}" if state.protocol_name.upper() == 'CPQR' else "N/A"
        return topo, pdr, tput, q_text, status, f"Early PDR: {state.early_pdr:.1%}"

def run_sim_task(proto, n, speed, load, dur):
    p_map = {'AODV': AODV, 'OLSR': OLSR, 'CPQR': CPQR}
    config = SimConfig(num_nodes=n, max_speed=speed, packet_rate=load, duration=dur)
    engine = SimulationEngine(p_map[proto], config, RandomWaypointMobility)
    engine.on_snapshot_cb = lambda t, s: update_metrics(engine)
    engine.on_step_cb = lambda t: update_topology(engine)
    
    state.reset()
    with state.lock:
        state.protocol_name = proto
    
    engine.run(real_time=True)
    update_topology(engine)
    update_metrics(engine)
    with state.lock: state.finished = True

@app.callback(Output('tick', 'disabled'), Input('restart-btn', 'n_clicks'), [State('protocol-dropdown', 'value'), State('nodes-slider', 'value'), State('speed-slider', 'value'), State('load-slider', 'value')])
def start_click(n, proto, nodes, speed, load):
    if n:
        threading.Thread(target=run_sim_task, args=(proto, nodes, speed, load, 300), daemon=True).start()
    return False

def run_dashboard(port=8050): app.run(debug=False, port=port, host='0.0.0.0')
if __name__ == '__main__': run_dashboard()
