import dash
from dash import dcc, html
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go
import threading
import time
import numpy as np
from simulation.engine import SimulationEngine
from config import SimConfig
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR
from core.mobility import RandomWaypointMobility

class DashboardState:
    def __init__(self):
        self.lock = threading.Lock()
        self.topology = {'nodes': [], 'edges': []}
        self.metrics_history = []
        self.finished = False

state = DashboardState()

app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("SOMRN Dashboard (Debug Mode)"),
    html.Div([
        html.Label("Protocol:"),
        dcc.Dropdown(id='proto', options=[{'label': 'CPQR', 'value': 'CPQR'}, {'label': 'AODV', 'value': 'AODV'}], value='CPQR'),
        html.Button("START SIMULATION", id='start-btn', n_clicks=0),
    ]),
    html.Div(id='status', children="Ready."),
    dcc.Graph(id='topo-graph'),
    dcc.Interval(id='timer', interval=1000)
])

@app.callback(Output('status', 'children'), Input('start-btn', 'n_clicks'), [State('proto', 'value')])
def start_sim(n, proto):
    print(f"DEBUG: Start clicked (n={n})", flush=True)
    if n == 0: return "Ready."
    def run():
        print(f"DEBUG: Thread started for {proto}", flush=True)
        p_map = {'AODV': AODV, 'OLSR': OLSR, 'CPQR': CPQR}
        config = SimConfig(num_nodes=20, duration=60)
        engine = SimulationEngine(p_map[proto], config, RandomWaypointMobility)
        engine.on_step_cb = lambda t: setattr(state, 'topology', engine.get_topology_for_dashboard())
        engine.run(real_time=True)
        state.finished = True
        print("DEBUG: Thread finished", flush=True)
    threading.Thread(target=run, daemon=True).start()
    return f"Running {proto}..."

@app.callback(Output('topo-graph', 'figure'), Input('timer', 'n_intervals'))
def update_topo(n):
    with state.lock:
        nodes = state.topology.get('nodes', [])
        fig = go.Figure()
        if nodes:
            fig.add_trace(go.Scatter(x=[n['x'] for n in nodes], y=[n['y'] for n in nodes], mode='markers+text', text=[str(n['id']) for n in nodes]))
        fig.update_layout(xaxis=dict(range=[0, 500]), yaxis=dict(range=[0, 500]))
        return fig

def run_dashboard(port=8888):
    app.run(debug=False, port=port, host='0.0.0.0')

if __name__ == '__main__':
    run_dashboard()
