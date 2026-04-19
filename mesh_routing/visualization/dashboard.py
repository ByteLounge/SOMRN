import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import threading
import time
from typing import Dict, List, Optional

# Shared state for the dashboard
class DashboardState:
    def __init__(self):
        self.lock = threading.Lock()
        self.topology = {'nodes': [], 'edges': []}
        self.metrics_history: List[dict] = []
        self.current_time = 0.0
        self.protocol_name = ""
        self.q_stats = {'mean': 0, 'max': 0, 'min': 0}

state = DashboardState()

def update_state(network, metrics_collector, t, protocol_name):
    with state.lock:
        state.topology = network.topology_snapshot()
        if metrics_collector.snapshots:
            state.metrics_history = [vars(s) for s in metrics_collector.snapshots]
        state.current_time = t
        state.protocol_name = protocol_name
        if hasattr(network, 'protocol') and hasattr(network.protocol, 'get_qtable_stats'):
             state.q_stats = network.protocol.get_qtable_stats()

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1(f"Wireless Mesh Network Live Dashboard"),
    html.Div(id='protocol-info', style={'fontSize': 24, 'marginBottom': 20}),
    
    html.Div([
        html.Div([
            html.H3("Network Topology"),
            dcc.Graph(id='topology-graph', style={'height': '600px'})
        ], style={'width': '60%', 'display': 'inline-block'}),
        
        html.Div([
            html.H3("Real-time Metrics"),
            dcc.Graph(id='metrics-chart', style={'height': '300px'}),
            dcc.Graph(id='throughput-chart', style={'height': '300px'})
        ], style={'width': '38%', 'display': 'inline-block', 'float': 'right'})
    ]),
    
    html.Div([
        html.H3("Q-Learning Stats (if CPQR)"),
        html.Div(id='q-stats-display')
    ]),
    
    dcc.Interval(id='interval-component', interval=1000, n_intervals=0)
])

@app.callback(
    [Output('topology-graph', 'figure'),
     Output('metrics-chart', 'figure'),
     Output('throughput-chart', 'figure'),
     Output('protocol-info', 'children'),
     Output('q-stats-display', 'children')],
    [Input('interval-component', 'n_intervals')]
)
def update_charts(n):
    with state.lock:
        # 1. Topology Figure
        node_x = [n['x'] for n in state.topology['nodes']]
        node_y = [n['y'] for n in state.topology['nodes']]
        
        edge_traces = []
        for edge in state.topology['edges']:
            source = next(n for n in state.topology['nodes'] if n['id'] == edge['source'])
            target = next(n for n in state.topology['nodes'] if n['id'] == edge['target'])
            
            # Color by quality (Red to Green)
            q = edge['quality']
            color = f'rgb({int(255*(1-q))}, {int(255*q)}, 0)'
            
            trace = go.Scatter(
                x=[source['x'], target['x'], None],
                y=[source['y'], target['y'], None],
                line=dict(width=2, color=color),
                hoverinfo='none',
                mode='lines'
            )
            edge_traces.append(trace)
            
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            text=[str(n['id']) for n in state.topology['nodes']],
            textposition="top center",
            marker=dict(size=15, color='royalblue', line_width=2)
        )
        
        topo_fig = go.Figure(data=edge_traces + [node_trace],
                             layout=go.Layout(
                                 showlegend=False,
                                 hovermode='closest',
                                 margin=dict(b=0,l=0,r=0,t=0),
                                 xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                 yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
                             ))

        # 2. Metrics Figure
        times = [m['time'] for m in state.metrics_history]
        pdrs = [m['pdr'] for m in state.metrics_history]
        delays = [m['avg_delay'] for m in state.metrics_history]
        
        metrics_fig = go.Figure()
        metrics_fig.add_trace(go.Scatter(x=times, y=pdrs, name='PDR', yaxis='y1'))
        metrics_fig.add_trace(go.Scatter(x=times, y=delays, name='Avg Delay (s)', yaxis='y2'))
        
        metrics_fig.update_layout(
            title="PDR and Delay",
            yaxis=dict(title="PDR", range=[0, 1]),
            yaxis2=dict(title="Delay (s)", overlaying='y', side='right'),
            margin=dict(l=40, r=40, t=40, b=40)
        )
        
        # 3. Throughput Figure
        tput = [m['throughput'] for m in state.metrics_history]
        tput_fig = go.Figure(data=[go.Scatter(x=times, y=tput, fill='tozeroy')])
        tput_fig.update_layout(title="Throughput (Bytes/s)", margin=dict(l=40, r=40, t=40, b=40))
        
        info = f"Protocol: {state.protocol_name} | Time: {state.current_time:.1f}s"
        
        q_info = f"Mean Q: {state.q_stats['mean']:.2f} | Max Q: {state.q_stats['max']:.2f} | Min Q: {state.q_stats['min']:.2f}"
        
        return topo_fig, metrics_fig, tput_fig, info, q_info

def run_dashboard(port=8050):
    app.run_server(debug=False, port=port, use_reloader=False)
