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

from simulation.engine import SimulationEngine
from config import SimConfig, ScenarioPresets
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR
from core.mobility import RandomWaypointMobility

class DashboardState:
    def __init__(self):
        self.lock = threading.Lock()
        self.topology = {'nodes': [], 'edges': [], 'packets': []}
        self.metrics_history: List[dict] = []
        self.current_time = 0.0
        self.protocol_name = ""
        self.q_stats = {'mean': 0, 'max': 0, 'min': 0}
        self.finished = False
        self.config = SimConfig()

state = DashboardState()

def update_state(network, protocol, metrics_history, t, protocol_name):
    with state.lock:
        snap = network.topology_snapshot()
        state.topology = snap
        state.metrics_history = metrics_history
        state.current_time = t
        state.protocol_name = protocol_name
        if protocol and hasattr(protocol, 'get_qtable_stats'):
             state.q_stats = protocol.get_qtable_stats()

app = dash.Dash(__name__, external_stylesheets=['https://codepen.io/chriddyp/pen/bWLwgP.css'])

# Cisco-like styling constants
CISCO_BLUE = "#005a9e"
GRID_COLOR = "#e5e5e5"
SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "300px",
    "padding": "20px",
    "background-color": "#f8f9fa",
    "border-right": "1px solid #dee2e6",
    "overflow-y": "auto",
    "z-index": 1000
}
CONTENT_STYLE = {
    "margin-left": "320px",
    "padding": "20px",
}

app.layout = html.Div([
    # Sidebar
    html.Div([
        html.Img(src="https://www.cisco.com/c/dam/en_us/about/ac49/ac20/images/logo_cisco_80x45.gif", style={'marginBottom': '20px'}),
        html.H4("Simulation Control", style={'color': CISCO_BLUE, 'fontWeight': 'bold'}),
        html.Hr(),
        
        html.Label("Protocol"),
        dcc.Dropdown(id='protocol-dropdown',
                     options=[{'label': 'AODV (Reactive)', 'value': 'AODV'},
                              {'label': 'OLSR (Proactive)', 'value': 'OLSR'},
                              {'label': 'CPQR (RL-based)', 'value': 'CPQR'}],
                     value='CPQR', clearable=False),
        
        html.Br(),
        html.Label("Number of Nodes"),
        dcc.Slider(id='nodes-slider', min=10, max=100, step=5, value=30, marks={i: str(i) for i in range(10, 101, 20)}),
        
        html.Label("Max Speed (m/s)"),
        dcc.Slider(id='speed-slider', min=0, max=30, step=1, value=5, marks={i: str(i) for i in range(0, 31, 5)}),
        
        html.Label("Packet Rate (pkts/s)"),
        dcc.Slider(id='load-slider', min=0.5, max=20, step=0.5, value=2, marks={i: str(i) for i in range(0, 21, 5)}),

        html.Label("Simulation Duration (s)"),
        dcc.Input(id='duration-input', type='number', value=300, style={'width': '100%'}),
        
        html.Br(), html.Br(),
        html.Button("START SIMULATION", id='restart-btn', style={'width': '100%', 'backgroundColor': CISCO_BLUE, 'color': 'white', 'border': 'none', 'padding': '10px'}),
        html.Br(), html.Br(),
        html.Button("EXPORT DATA (CSV)", id='export-btn', style={'width': '100%'}),
        html.Div(id='export-status', style={'fontSize': '12px', 'marginTop': '10px'}),
        
        html.Hr(),
        html.Div(id='q-table-panel', children=[
            html.H6("Q-Learning Intelligence"),
            html.Div(id='q-stats-display', style={'fontSize': '12px'}),
        ], style={'display': 'none'})
    ], style=SIDEBAR_STYLE),

    # Main Content
    html.Div([
        html.Div([
            html.H2("Wireless Mesh Network Dashboard", style={'display': 'inline-block', 'color': CISCO_BLUE}),
            html.Div(id='status-banner', style={'float': 'right', 'marginTop': '25px', 'fontWeight': 'bold'})
        ]),
        
        html.Div(id='protocol-info', style={'fontSize': '18px', 'marginBottom': '20px', 'color': '#666'}),

        html.Div([
            html.Div([
                html.H5("Logic Topology View (Packet Tracer Mode)", style={'textAlign': 'center'}),
                dcc.Graph(id='topology-graph', style={'height': '600px', 'border': f'1px solid {GRID_COLOR}'})
            ], className="eight columns"),
            
            html.Div([
                html.H5("Performance Metrics", style={'textAlign': 'center'}),
                dcc.Graph(id='metrics-chart', style={'height': '300px'}),
                dcc.Graph(id='throughput-chart', style={'height': '300px'})
            ], className="four columns")
        ], className="row"),
        
        dcc.Interval(id='interval-component', interval=1000, n_intervals=0)
    ], style=CONTENT_STYLE)
])

current_sim_thread = None

def run_simulation(protocol_name, n_nodes, speed, load, duration):
    protocol_map = {'AODV': AODV, 'OLSR': OLSR, 'CPQR': CPQR}
    config = SimConfig(
        num_nodes=n_nodes,
        max_speed=speed,
        packet_rate=load,
        duration=duration,
        seed=42 # Fixed seed for dashboard reproducibility
    )
    
    engine = SimulationEngine(protocol_map[protocol_name], config, RandomWaypointMobility)
    engine.on_snapshot_cb = lambda t, snap: update_state(
        engine.network, 
        engine.protocol, 
        [vars(s) for s in engine.metrics.snapshots], 
        t, 
        engine.protocol.name
    )
    
    with state.lock:
        state.finished = False
        state.metrics_history = []
        state.topology = {'nodes': [], 'edges': [], 'packets': []}
        state.current_time = 0.0
        state.config = config
        
    engine.run()
    with state.lock: state.finished = True

@app.callback(
    Output('protocol-info', 'children'),
    Input('restart-btn', 'n_clicks'),
    [State('protocol-dropdown', 'value'),
     State('nodes-slider', 'value'),
     State('speed-slider', 'value'),
     State('load-slider', 'value'),
     State('duration-input', 'value')],
    prevent_initial_call=True
)
def restart_sim(n_clicks, protocol, nodes, speed, load, duration):
    global current_sim_thread
    if current_sim_thread and current_sim_thread.is_alive():
        return "Wait for current simulation to finish or reload page."
    
    current_sim_thread = threading.Thread(
        target=run_simulation, 
        args=(protocol, nodes, speed, load, float(duration)), 
        daemon=True
    )
    current_sim_thread.start()
    return f"Initializing {protocol} with {nodes} nodes..."

@app.callback(
    [Output('topology-graph', 'figure'), 
     Output('metrics-chart', 'figure'), 
     Output('throughput-chart', 'figure'),
     Output('q-stats-display', 'children'),
     Output('status-banner', 'children'), 
     Output('q-table-panel', 'style')],
    [Input('interval-component', 'n_intervals')]
)
def update_charts(n):
    with state.lock:
        # 1. Topology with Cisco-like Markers
        nodes = state.topology.get('nodes', [])
        edge_traces = []
        
        # Draw links with quality-based color
        for edge in state.topology.get('edges', []):
            src = next((n for n in nodes if n['id'] == edge['source']), None)
            tgt = next((n for n in nodes if n['id'] == edge['target']), None)
            if not src or not tgt: continue
            q = edge['quality']
            # Cisco green/amber/red status links
            color = "#28a745" if q > 0.8 else "#ffc107" if q > 0.4 else "#dc3545"
            edge_traces.append(go.Scatter(
                x=[src['x'], tgt['x'], None], y=[src['y'], tgt['y'], None],
                line=dict(width=1, color=color),
                hoverinfo='none', mode='lines', opacity=0.4
            ))
        
        # Packet animations
        packet_x, packet_y = [], []
        for pkt in state.topology.get('packets', []):
            src = next((n for n in nodes if n['id'] == pkt['source']), None)
            tgt = next((n for n in nodes if n['id'] == pkt['target']), None)
            if src and tgt:
                packet_x.append((src['x'] + tgt['x']) / 2)
                packet_y.append((src['y'] + tgt['y']) / 2)
        
        node_trace = go.Scatter(
            x=[n['x'] for n in nodes], y=[n['y'] for n in nodes],
            mode='markers+text',
            text=[str(n['id']) for n in nodes],
            textposition="bottom center",
            hovertext=[f"Node {n['id']}<br>Energy: {n['energy']:.1f}%" for n in nodes],
            marker=dict(
                size=18,
                symbol='circle',
                color=CISCO_BLUE,
                line=dict(width=2, color="white")
            )
        )
        
        packet_trace = go.Scatter(
            x=packet_x, y=packet_y, 
            mode='markers', 
            marker=dict(size=6, color='black', symbol='square'),
            name='Packets'
        )
        
        area_size = state.config.area_size
        topo_fig = go.Figure(
            data=edge_traces + [node_trace, packet_trace],
            layout=go.Layout(
                showlegend=False, 
                margin=dict(b=0,l=0,r=0,t=0),
                xaxis=dict(range=[0, area_size], showgrid=True, gridcolor=GRID_COLOR, zeroline=False, dtick=50),
                yaxis=dict(range=[0, area_size], showgrid=True, gridcolor=GRID_COLOR, zeroline=False, dtick=50),
                plot_bgcolor='white'
            )
        )

        # 2. Metrics History
        history = state.metrics_history
        times = [m['time'] for m in history]
        
        metrics_fig = go.Figure()
        metrics_fig.add_trace(go.Scatter(x=times, y=[m['pdr'] for m in history], name='PDR', line=dict(color=CISCO_BLUE)))
        metrics_fig.update_layout(title="Packet Delivery Ratio", yaxis=dict(range=[0, 1.1]), margin=dict(t=30, b=30))

        tput_fig = go.Figure()
        tput_fig.add_trace(go.Scatter(x=times, y=[m['throughput_bps']/1000 for m in history], fill='tozeroy', name='kbps', line=dict(color="#28a745")))
        tput_fig.update_layout(title="Throughput (kbps)", margin=dict(t=30, b=30))
        
        q_info = f"Avg Q: {state.q_stats['mean']:.2f} | Convergence: {state.q_stats['min']:.2f}-{state.q_stats['max']:.2f}"
        status = html.Span("● LIVE", style={'color': '#28a745'}) if not state.finished and times else html.Span("■ IDLE", style={'color': '#666'})
        if state.finished: status = html.Span("✓ COMPLETE", style={'color': CISCO_BLUE})
        
        q_style = {'display': 'block'} if state.protocol_name == 'CPQR' else {'display': 'none'}
        
        return topo_fig, metrics_fig, tput_fig, q_info, status, q_style

@app.callback(Output('export-status', 'children'), Input('export-btn', 'n_clicks'), prevent_initial_call=True)
def export_metrics(n_clicks):
    with state.lock:
        if not state.metrics_history: return "No data to export."
        df = pd.DataFrame(state.metrics_history)
        os.makedirs("results", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"results/dashboard_export_{ts}.csv"
        df.to_csv(path, index=False)
        return f"Saved to {path}"

def run_dashboard(port=8050):
    app.run(debug=False, port=port)

if __name__ == '__main__':
    run_dashboard()
