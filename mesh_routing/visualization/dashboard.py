from dash import Dash, html, dcc
import plotly.graph_objects as go
from dash.dependencies import Input, Output
import threading

app = Dash(__name__)

# Shared state between simulation and dashboard
class DashboardState:
    def __init__(self):
        self.lock = threading.Lock()
        self.network = None
        self.metrics_history = []
        self.time = 0.0
        self.protocol_name = ""
        self.baseline_stats = {} # Optional

state = DashboardState()

def update_state(network_snap, metrics_history, t, protocol_name):
    with state.lock:
        state.network = network_snap
        state.metrics_history = list(metrics_history)
        state.time = t
        state.protocol_name = protocol_name

app.layout = html.Div([
    html.H1("Wireless Mesh Network Simulation Dashboard"),
    html.Div(id='protocol-info', style={'fontSize': 20, 'marginBottom': 20}),
    
    html.Div([
        html.Div([
            dcc.Graph(id='topology-graph', animate=False)
        ], style={'width': '50%', 'display': 'inline-block'}),
        
        html.Div([
            dcc.Graph(id='metrics-graph', animate=False)
        ], style={'width': '50%', 'display': 'inline-block'})
    ]),
    
    dcc.Interval(
        id='interval-component',
        interval=1000, # in milliseconds
        n_intervals=0
    )
])

@app.callback(
    Output('protocol-info', 'children'),
    Input('interval-component', 'n_intervals')
)
def update_info(n):
    with state.lock:
        return f"Protocol: {state.protocol_name} | Time: {state.time:.1f}s"

@app.callback(
    Output('topology-graph', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_topology(n):
    with state.lock:
        net = state.network
        if not net:
            return go.Figure()

    nodes = net['nodes']
    edges = net['edges']
    
    node_x = [n['x'] for n in nodes]
    node_y = [n['y'] for n in nodes]
    node_text = [f"Node {n['id']}" for n in nodes]
    
    edge_x = []
    edge_y = []
    node_pos = {n['id']: (n['x'], n['y']) for n in nodes}
    for e in edges:
        u, v = e['source'], e['target']
        x0, y0 = node_pos[u]
        x1, y1 = node_pos[v]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])
        
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.5, color='#888'),
        hoverinfo='none',
        mode='lines'
    ))
    
    fig.add_trace(go.Scatter(
        x=node_x, y=node_y,
        mode='markers+text',
        text=[str(n['id']) for n in nodes],
        textposition="top center",
        marker=dict(
            showscale=False,
            color='blue',
            size=10,
            line_width=2
        ),
        hovertext=node_text
    ))
    
    fig.update_layout(
        title="Live Topology",
        showlegend=False,
        hovermode='closest',
        margin=dict(b=0,l=0,r=0,t=40),
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    )
    return fig

@app.callback(
    Output('metrics-graph', 'figure'),
    Input('interval-component', 'n_intervals')
)
def update_metrics(n):
    with state.lock:
        history = list(state.metrics_history)
        
    if not history:
        return go.Figure()
        
    times = [s.time for s in history]
    pdrs = [s.pdr for s in history]
    delays = [s.avg_delay for s in history]
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=times, y=pdrs, name='PDR', mode='lines+markers'))
    fig.add_trace(go.Scatter(x=times, y=delays, name='Avg Delay (s)', mode='lines+markers', yaxis='y2'))
    
    fig.update_layout(
        title="Real-time Metrics",
        xaxis_title="Time (s)",
        yaxis_title="PDR",
        yaxis2=dict(
            title="Delay (s)",
            overlaying="y",
            side="right"
        ),
        margin=dict(b=40,l=40,r=40,t=40)
    )
    return fig

def run(port=8050):
    # Suppress dash output
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run_server(debug=False, port=port, host='0.0.0.0')
