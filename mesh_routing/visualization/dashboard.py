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

class DashboardState:
    def __init__(self):
        self.lock = threading.Lock()
        self.topology = {'nodes': [], 'edges': [], 'packets': []}
        self.metrics_history: List[dict] = []
        self.current_time = 0.0
        self.protocol_name = ""
        self.q_stats = {'mean': 0, 'max': 0, 'min': 0}
        self.finished = False

state = DashboardState()

def update_state(network, protocol, metrics_history, t, protocol_name):
    """BUG 1 Fix: Correct signature and attribute access."""
    with state.lock:
        snap = network.topology_snapshot()
        state.topology = snap
        state.metrics_history = metrics_history
        state.current_time = t
        state.protocol_name = protocol_name
        # Using protocol directly instead of network.protocol
        if protocol and hasattr(protocol, 'get_qtable_stats'):
             state.q_stats = protocol.get_qtable_stats()

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1(f"Wireless Mesh Network Live Dashboard"),
    html.Div(id='protocol-info', style={'fontSize': 24, 'marginBottom': 10}),
    html.Div(id='status-banner', style={'fontSize': 20, 'color': 'red', 'fontWeight': 'bold', 'marginBottom': 20}),
    
    html.Div([
        html.Label("Protocol: "),
        dcc.Dropdown(id='protocol-dropdown',
                     options=[{'label': 'AODV', 'value': 'AODV'},
                              {'label': 'OLSR', 'value': 'OLSR'},
                              {'label': 'CPQR', 'value': 'CPQR'}],
                     value='CPQR', style={'width': '200px', 'display': 'inline-block'}),
        html.Label(" Scenario: ", style={'marginLeft': '20px'}),
        dcc.Dropdown(id='scenario-dropdown',
                     options=[{'label': 'Default', 'value': 'default'},
                              {'label': 'Static', 'value': 'static'},
                              {'label': 'Mobile', 'value': 'mobile'},
                              {'label': 'Stress', 'value': 'stress'}],
                     value='default', style={'width': '200px', 'display': 'inline-block'}),
        html.Button("Restart Simulation", id='restart-btn', style={'marginLeft': '20px'}),
        html.Button("Export Metrics CSV", id='export-btn', style={'marginLeft': '20px'}),
        html.Div(id='export-status', style={'display': 'inline-block', 'marginLeft': '10px'})
    ], style={'marginBottom': '20px'}),
    
    html.Div([
        html.Div([
            html.H3("Network Topology"),
            dcc.Graph(id='topology-graph', style={'height': '500px'})
        ], style={'width': '50%', 'display': 'inline-block'}),
        html.Div([
            html.H3("Real-time Metrics"),
            dcc.Graph(id='metrics-chart', style={'height': '250px'}),
            dcc.Graph(id='throughput-chart', style={'height': '250px'})
        ], style={'width': '48%', 'display': 'inline-block', 'float': 'right'})
    ]),
    
    html.Div(id='q-table-panel', children=[
        html.H3("Q-Learning Stats (CPQR only)"),
        html.Div(id='q-stats-display'),
        dcc.Graph(id='q-heatmap-chart', style={'height': '300px'})
    ], style={'display': 'none'}),
    
    dcc.Interval(id='interval-component', interval=1000, n_intervals=0)
])

from simulation.engine import SimulationEngine
from config import SimConfig, ScenarioPresets
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR
from core.mobility import RandomWaypointMobility

current_sim_thread = None
stop_sim_flag = False

def run_simulation(protocol_name, scenario_name):
    global stop_sim_flag
    protocol_map = {'AODV': AODV, 'OLSR': OLSR, 'CPQR': CPQR}
    if scenario_name == 'static': config = ScenarioPresets.static_low_load()
    elif scenario_name == 'mobile': config = ScenarioPresets.mobile_high_load()
    elif scenario_name == 'stress': config = ScenarioPresets.stress_test()
    else: config = SimConfig()
    
    engine = SimulationEngine(protocol_map[protocol_name], config, RandomWaypointMobility)
    # Correct call site in run_simulation
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
        
    engine.run()
    with state.lock: state.finished = True

@app.callback(Output('export-status', 'children'), Input('export-btn', 'n_clicks'), prevent_initial_call=True)
def export_metrics(n_clicks):
    try:
        with state.lock:
            if not state.metrics_history: return "No data."
            df = pd.DataFrame(state.metrics_history)
            os.makedirs("results", exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = f"results/dashboard_export_{ts}.csv"
            df.to_csv(path, index=False)
            return f"Saved to {path}"
    except Exception as e: return f"Error: {e}"

@app.callback(Output('protocol-info', 'children'), Input('restart-btn', 'n_clicks'), State('protocol-dropdown', 'value'), State('scenario-dropdown', 'value'), prevent_initial_call=True)
def restart_sim(n_clicks, protocol, scenario):
    global current_sim_thread, stop_sim_flag
    if current_sim_thread and current_sim_thread.is_alive(): return "Sim already running"
    current_sim_thread = threading.Thread(target=run_simulation, args=(protocol, scenario), daemon=True)
    current_sim_thread.start()
    return f"Restarting with {protocol}..."

@app.callback(
    [Output('topology-graph', 'figure'), Output('metrics-chart', 'figure'), Output('throughput-chart', 'figure'),
     Output('protocol-info', 'children', allow_duplicate=True), Output('q-stats-display', 'children'),
     Output('status-banner', 'children'), Output('q-table-panel', 'style')],
    [Input('interval-component', 'n_intervals')],
    prevent_initial_call=True
)
def update_charts(n):
    try:
        with state.lock:
            nodes = state.topology.get('nodes', [])
            edge_traces = []
            for edge in state.topology.get('edges', []):
                src = next((n for n in nodes if n['id'] == edge['source']), None)
                tgt = next((n for n in nodes if n['id'] == edge['target']), None)
                if not src or not tgt: continue
                q = edge['quality']
                edge_traces.append(go.Scatter(x=[src['x'], tgt['x'], None], y=[src['y'], tgt['y'], None],
                                             line=dict(width=2, color=f'rgb({int(255*(1-q))}, {int(255*q)}, 0)'),
                                             hoverinfo='none', mode='lines'))
            
            packet_x, packet_y = [], []
            for pkt in state.topology.get('packets', []):
                src = next((n for n in nodes if n['id'] == pkt['source']), None)
                tgt = next((n for n in nodes if n['id'] == pkt['target']), None)
                if src and tgt:
                    packet_x.append((src['x'] + tgt['x']) / 2)
                    packet_y.append((src['y'] + tgt['y']) / 2)
            
            node_trace = go.Scatter(x=[n['x'] for n in nodes], y=[n['y'] for n in nodes], mode='markers+text',
                                    text=[str(n['id']) for n in nodes], textposition="top center",
                                    marker=dict(size=15, color='royalblue'))
            packet_trace = go.Scatter(x=packet_x, y=packet_y, mode='markers', marker=dict(size=8, color='black'))
            
            topo_fig = go.Figure(data=edge_traces + [node_trace, packet_trace],
                                 layout=go.Layout(showlegend=False, margin=dict(b=0,l=0,r=0,t=0),
                                                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)))

            history = state.metrics_history
            times = [m['time'] for m in history]
            metrics_fig = go.Figure()
            metrics_fig.add_trace(go.Scatter(x=times, y=[m['pdr'] for m in history], name='PDR', yaxis='y1'))
            metrics_fig.add_trace(go.Scatter(x=times, y=[m['avg_delay'] for m in history], name='Delay', yaxis='y2'))
            metrics_fig.update_layout(yaxis=dict(title="PDR", range=[0, 1]), yaxis2=dict(title="Delay", overlaying='y', side='right'))

            tput_fig = go.Figure(data=[go.Scatter(x=times, y=[m['throughput_bps'] for m in history], fill='tozeroy')])
            tput_fig.update_layout(title="Throughput (bps)")
            
            info = f"Protocol: {state.protocol_name} | Time: {state.current_time:.1f}s"
            q_info = f"Mean Q: {state.q_stats['mean']:.2f} | Max Q: {state.q_stats['max']:.2f}"
            status = "Simulation Complete" if state.finished else ""
            q_style = {'display': 'block'} if state.protocol_name == 'CPQR' else {'display': 'none'}
            
            return topo_fig, metrics_fig, tput_fig, info, q_info, status, q_style
    except Exception as e: return [dash.no_update]*7

def run_dashboard(port=8050):
    app.run_server(debug=False, port=port, use_reloader=False)
