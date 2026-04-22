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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

from simulation.engine import SimulationEngine
from config import SimConfig, ScenarioPresets
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR
from core.mobility import RandomWaypointMobility
from core.node import Node
from core.packet import Packet

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
        
        # Phase 1 & 2 additions
        self.completed_routes: List[dict] = []
        self.animated_route_idx = 0
        self.current_animating_path: List[int] = []
        self.animating_hop_idx = 0
        self.animating_packet_id = ""
        
        # Interactive Mode State
        self.interactive_nodes = [] # [{'id': 0, 'x': 100, 'y': 100, 'type': 'router'}]
        self.interactive_src = None
        self.interactive_dst = None
        self.interactive_protocol = 'CPQR'
        self.interactive_tx_range = 150.0
        self.narration = "Welcome! Place some devices and start a journey."

state = DashboardState()

# Device Icon Mappings
ICONS = {
    'router': '🔴 Router (Hexagon)',
    'pc': '🖥️ PC (Square)',
    'laptop': '💻 Laptop (Diamond)',
    'access_point': '📡 AP (Star)'
}
UNICODE_ICONS = {
    'router': '⬢',
    'pc': '🖥️',
    'laptop': '💻',
    'access_point': '📡'
}
SYMBOLS = {
    'router': 'hexagon',
    'pc': 'square',
    'laptop': 'diamond',
    'access_point': 'star'
}

def update_topology(engine):
    """Updates only the topology state for smooth animation."""
    with state.lock:
        state.topology = engine.get_topology_for_dashboard()
        state.current_time = engine.time
        
        # Fetch new completed routes
        new_routes = engine.get_last_packet_routes()
        if new_routes:
            state.completed_routes.extend(new_routes)
            if len(state.completed_routes) > 10:
                state.completed_routes = state.completed_routes[-10:]

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
    """Updates the metrics history on snapshot intervals."""
    with state.lock:
        state.metrics_history = [vars(s) for s in engine.metrics.snapshots]
        state.protocol_name = engine.protocol.name
        state.congestion_events = getattr(engine.metrics, 'congestion_events', 0)
        state.early_pdr = getattr(engine.metrics, 'early_pdr', 0.0)

app = dash.Dash(__name__, external_stylesheets=['https://codepen.io/chriddyp/pen/bWLwgP.css'], suppress_callback_exceptions=True)

# CSS to disable the default Dash loading overlay which causes flickering
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            ._dash-loading {
                display: none !important;
            }
            .dash-spinner {
                display: none !important;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

# Cisco-like styling constants
CISCO_BLUE = "#005a9e"
GRID_COLOR = "#e5e5e5"
SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "320px",
    "padding": "20px",
    "background-color": "#f8f9fa",
    "border-right": "1px solid #dee2e6",
    "overflow-y": "auto",
    "z-index": 1000
}
CONTENT_STYLE = {
    "margin-left": "340px",
    "padding": "20px",
}

# --- LAYOUT COMPONENTS ---

def get_research_sidebar():
    return html.Div([
        html.H3("SOMRN DASHBOARD", style={'color': CISCO_BLUE, 'fontWeight': 'bold', 'textAlign': 'center', 'marginBottom': '30px', 'borderBottom': f'2px solid {CISCO_BLUE}', 'paddingBottom': '10px'}),
        html.H4("Simulation Control", style={'color': CISCO_BLUE, 'fontWeight': 'bold'}),
        html.Hr(),
        
        html.Label("Protocol"),
        html.Div(dcc.Dropdown(id='protocol-dropdown',
                     options=[{'label': 'AODV (Reactive)', 'value': 'AODV'},
                              {'label': 'OLSR (Proactive)', 'value': 'OLSR'},
                              {'label': 'CPQR (RL-based)', 'value': 'CPQR'}],
                     value='CPQR', clearable=False),
                 title="Select the routing protocol to evaluate. CPQR uses AI to find the best paths."),
        
        html.Br(),
        html.Label("Number of Nodes"),
        html.Div(dcc.Slider(id='nodes-slider', min=10, max=100, step=5, value=30, marks={i: str(i) for i in range(10, 101, 20)}),
                 title="Adjust the total number of devices in the network."),
        
        html.Label("Max Speed (m/s)"),
        html.Div(dcc.Slider(id='speed-slider', min=0, max=30, step=1, value=5, marks={i: str(i) for i in range(0, 31, 5)}),
                 title="Set how fast nodes move (0 = static, 30 = very fast)."),
        
        html.Label("Packet Rate (pkts/s)"),
        html.Div(dcc.Slider(id='load-slider', min=0.5, max=20, step=0.5, value=2, marks={i: str(i) for i in range(0, 21, 5)}),
                 title="Control the intensity of data traffic generated."),

        html.Label("Simulation Duration (s)"),
        html.Div(dcc.Input(id='duration-input', type='number', value=300, style={'width': '100%'}),
                 title="How long the simulation should run in seconds."),
        
        html.Br(), html.Br(),
        html.Button("START SIMULATION", id='restart-btn', style={'width': '100%', 'backgroundColor': CISCO_BLUE, 'color': 'white', 'border': 'none', 'padding': '10px'}),
        html.Br(), html.Br(),
        html.Button("EXPORT DATA (CSV)", id='export-btn', style={'width': '100%'}),
        html.Div(id='export-status', style={'fontSize': '12px', 'marginTop': '10px'}),
        
        html.Hr(),
        html.Div(id='q-table-panel', children=[
            html.H6("Q-Learning Intelligence"),
            html.Div(id='q-stats-display', style={'fontSize': '12px'}),
            html.Div(id='cpqr-intelligence-status', style={'fontSize': '12px', 'marginTop': '10px'}),
        ], style={'display': 'none'})
    ], id='research-sidebar')

def get_interactive_sidebar():
    return html.Div([
        html.H3("Interactive Mode", style={'color': CISCO_BLUE, 'fontWeight': 'bold', 'textAlign': 'center'}),
        html.Hr(),
        
        html.Label("Add Device"),
        html.Div(dcc.Dropdown(id='device-type-dropdown',
                     options=[{'label': v, 'value': k} for k, v in ICONS.items()],
                     value='router', clearable=False),
                 title="Pick a network device type to add to your custom mesh."),
        html.Button("Add Device to Canvas", id='add-device-btn', style={'width': '100%', 'marginTop': '10px'},
                    title="Click to place the selected device at a random location on the map."),
        html.Button("Clear Canvas", id='clear-canvas-btn', style={'width': '100%', 'marginTop': '5px', 'backgroundColor': '#dc3545', 'color': 'white'},
                    title="Remove all devices and reset the network topology."),
        
        html.Hr(),
        html.Label("Quick Setup"),
        html.Div(dcc.Input(id='quick-nodes-input', type='number', min=5, max=20, value=10, style={'width': '100%'}),
                  title="Specify how many nodes you want to place automatically."),
        html.Button("Auto-Place Nodes", id='auto-place-btn', style={'width': '100%', 'marginTop': '5px'},
                    title="Instantly create a circular network with the chosen number of devices."),
        
        html.Hr(),
        html.Label("Transmission Range (m)"),
        html.Div(dcc.Slider(id='tx-range-slider', min=50, max=300, step=10, value=150, marks={i: str(i) for i in range(50, 301, 50)}),
                 title="Nodes within this distance can communicate directly."),
        
        html.Hr(),
        html.Label("📤 Source Node"),
        html.Div(dcc.Dropdown(id='source-dropdown', options=[], placeholder="Select Source"),
                 title="This is where your data packet starts its journey — think of it as the sender's device."),
        
        html.Br(),
        html.Label("📥 Destination Node"),
        html.Div(dcc.Dropdown(id='destination-dropdown', options=[], placeholder="Select Destination"),
                 title="This is where your data packet needs to go — the final recipient."),
        
        html.Hr(),
        html.Label("Choose Routing Protocol"),
        html.Div(dcc.RadioItems(id='interactive-protocol-radio',
                       options=[{'label': '🧠 CPQR (AI-Powered)', 'value': 'CPQR'},
                                {'label': '📡 AODV (Reactive)', 'value': 'AODV'},
                                {'label': '🗺️ OLSR (Proactive)', 'value': 'OLSR'}],
                       value='CPQR'),
                 title="CPQR uses Artificial Intelligence to learn which paths are least congested and most reliable."),
        
        html.Br(),
        html.Button("▶ START PACKET JOURNEY", id='start-journey-btn', style={'width': '100%', 'backgroundColor': CISCO_BLUE, 'color': 'white', 'fontWeight': 'bold', 'height': '50px'})
    ], id='interactive-sidebar')

app.layout = html.Div([
    # Sidebar Containers
    html.Div(id='research-sidebar-container', style=SIDEBAR_STYLE, children=get_research_sidebar()),
    html.Div(id='interactive-sidebar-container', style={**SIDEBAR_STYLE, 'display': 'none'}, children=get_interactive_sidebar()),

    # Main Content Container
    html.Div([
        dcc.Tabs(id='main-tabs', value='research', children=[
            dcc.Tab(label='📊 Research Mode (Advanced)', value='research', style={'fontWeight': 'bold'}, selected_style={'backgroundColor': CISCO_BLUE, 'color': 'white'}),
            dcc.Tab(label='🖥️ Interactive Mode (Beginner)', value='interactive', style={'fontWeight': 'bold'}, selected_style={'backgroundColor': CISCO_BLUE, 'color': 'white'}),
        ]),

        # Research Mode Content
        html.Div(id='research-content', style={'marginTop': '20px'}, children=[
            html.Div([
                html.H2("Wireless Mesh Network Dashboard", style={'display': 'inline-block', 'color': CISCO_BLUE}),
                html.Div(id='status-banner', style={'float': 'right', 'marginTop': '25px', 'fontWeight': 'bold'})
            ]),
            html.Div(id='protocol-info', style={'fontSize': '18px', 'marginBottom': '20px', 'color': '#666'}),
            html.Div([
                html.Div([
                    html.H5("Logic Topology View (Packet Tracer Mode)", style={'textAlign': 'center'}),
                    html.Div(dcc.Graph(id='topology-graph', figure=EMPTY_FIG, style={'height': '600px', 'border': f'1px solid {GRID_COLOR}'}),
                             title="The network map showing nodes and their links. Watch packets move hop-by-hop."),
                    html.Div(id='animation-status', style={'textAlign': 'center', 'fontSize': '14px', 'marginTop': '10px', 'fontWeight': 'bold'})
                ], className="eight columns"),
                html.Div([
                    html.H5("Performance Metrics", style={'textAlign': 'center'}),
                    dcc.Graph(id='metrics-chart', figure=EMPTY_FIG, style={'height': '300px'}),
                    html.Div(id='early-pdr-display', style={'textAlign': 'center', 'fontWeight': 'bold', 'color': CISCO_BLUE, 'marginBottom': '10px'}),
                    dcc.Graph(id='throughput-chart', figure=EMPTY_FIG, style={'height': '300px'}),
                    dcc.Graph(id='reward-chart', figure=EMPTY_FIG, style={'height': '300px'})
                ], className="four columns")
            ], className="row")
        ]),

        # Interactive Mode Content
        html.Div(id='interactive-content', style={'marginTop': '20px', 'display': 'none'}, children=[
            html.H2("Interactive Packet Journey", style={'color': CISCO_BLUE}),
            html.Div([
                html.Div([
                    html.Div(dcc.Graph(id='interactive-canvas', figure=EMPTY_FIG, style={'height': '600px', 'border': f'1px solid {CISCO_BLUE}'}),
                             title="Click 'Add Device' to build your network, then select a Source and Destination to start a packet journey."),
                    html.Div(id='interactive-animation-status', style={'textAlign': 'center', 'fontSize': '14px', 'marginTop': '10px', 'fontWeight': 'bold'})
                ], className="nine columns"),
                html.Div([
                    html.H5("📚 Legend"),
                    html.Table([
                        html.Tr([html.Td("🟢", style={'fontSize': '20px'}), html.Td("Source Node")]),
                        html.Tr([html.Td("🔴", style={'fontSize': '20px'}), html.Td("Destination Node")]),
                        html.Tr([html.Td("🔵", style={'fontSize': '20px'}), html.Td("Intermediate Node")]),
                        html.Tr([html.Td("🟡", style={'fontSize': '20px'}), html.Td("Active Forwarder")]),
                        html.Tr([html.Td(html.Div(style={'width': '20px', 'height': '2px', 'backgroundColor': '#00FF88'}), style={'padding': '10px'}), html.Td("Healthy Link")]),
                        html.Tr([html.Td(html.Div(style={'width': '20px', 'height': '2px', 'backgroundColor': '#FFA500'}), style={'padding': '10px'}), html.Td("Congested Link")]),
                        html.Tr([html.Td(html.Div(style={'width': '20px', 'height': '2px', 'backgroundColor': '#FF4444'}), style={'padding': '10px'}), html.Td("Weak Link")])
                    ], style={'width': '100%'})
                ], className="three columns")
            ], className="row"),
            html.Br(),
            html.Div([
                html.H4("📖 What's Happening?"),
                html.Div(id='narration-panel', style={'padding': '15px', 'backgroundColor': '#f8f9fa', 'borderLeft': f'5px solid {CISCO_BLUE}', 'fontSize': '18px'})
            ])
        ])
    ], style=CONTENT_STYLE),
    
    dcc.Interval(id='interval-component', interval=500, n_intervals=0),
    dcc.Interval(id='interval-component-slow', interval=2000, n_intervals=0),
    dcc.Interval(id='animation-interval', interval=300, n_intervals=0)
])

# Default empty figure to prevent flickering but remain visible
EMPTY_FIG = go.Figure(layout=go.Layout(
    xaxis=dict(visible=True, range=[0, 500], showgrid=True, gridcolor=GRID_COLOR),
    yaxis=dict(visible=True, range=[0, 500], showgrid=True, gridcolor=GRID_COLOR),
    plot_bgcolor='white', paper_bgcolor='white',
    margin=dict(l=40, r=20, t=40, b=40),
    uirevision='constant'
))

# --- TAB CONTENT RENDERING ---

@app.callback(
    [Output('research-content', 'style'),
     Output('interactive-content', 'style'),
     Output('research-sidebar-container', 'style'),
     Output('interactive-sidebar-container', 'style')],
    [Input('main-tabs', 'value')]
)
def toggle_tabs(tab):
    logger.info(f"Toggling to tab: {tab}")
    res_display = {'marginTop': '20px'} if tab == 'research' else {'display': 'none'}
    int_display = {'marginTop': '20px'} if tab == 'interactive' else {'display': 'none'}
    res_side = SIDEBAR_STYLE if tab == 'research' else {**SIDEBAR_STYLE, 'display': 'none'}
    int_side = SIDEBAR_STYLE if tab == 'interactive' else {**SIDEBAR_STYLE, 'display': 'none'}
    return res_display, int_display, res_side, int_side

# --- INTERACTIVE MODE CALLBACKS ---

@app.callback(
    [Output('interactive-canvas', 'figure'),
     Output('source-dropdown', 'options'),
     Output('destination-dropdown', 'options'),
     Output('narration-panel', 'children')],
    [Input('add-device-btn', 'n_clicks'),
     Input('clear-canvas-btn', 'n_clicks'),
     Input('auto-place-btn', 'n_clicks'),
     Input('source-dropdown', 'value'),
     Input('destination-dropdown', 'value'),
     Input('tx-range-slider', 'value'),
     Input('animation-interval', 'n_intervals')],
    [State('device-type-dropdown', 'value'),
     State('quick-nodes-input', 'value'),
     State('main-tabs', 'value')]
)
def update_interactive_canvas(add_n, clear_n, auto_n, src, dst, tx_range, anim_n, device_type, quick_n, active_tab):
    if active_tab != 'interactive':
        return [dash.no_update]*4

    ctx = dash.callback_context
    trigger = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else ""
    
    with state.lock:
        # PERFORMANCE: Only update on interval if an animation is actually happening
        if trigger == 'animation-interval' and not state.current_animating_path:
            return [dash.no_update]*4

        if trigger == 'clear-canvas-btn':
            state.interactive_nodes = []
            state.interactive_src = None
            state.interactive_dst = None
            state.narration = "Canvas cleared. Place some devices!"
        elif trigger == 'add-device-btn' and len(state.interactive_nodes) < 20:
            new_id = len(state.interactive_nodes)
            state.interactive_nodes.append({
                'id': new_id,
                'x': np.random.uniform(50, 450),
                'y': np.random.uniform(50, 450),
                'type': device_type
            })
            state.narration = f"Added {ICONS[device_type]} as Node {new_id}."
        elif trigger == 'auto-place-btn':
            state.interactive_nodes = []
            types = list(ICONS.keys())
            for i in range(quick_n):
                state.interactive_nodes.append({
                    'id': i,
                    'x': 250 + 150 * np.cos(2 * np.pi * i / quick_n),
                    'y': 250 + 150 * np.sin(2 * np.pi * i / quick_n),
                    'type': np.random.choice(types)
                })
            state.narration = f"Placed {quick_n} devices in a circular layout."
        
        state.interactive_src = src
        state.interactive_dst = dst
        state.interactive_tx_range = tx_range
        
        # If no nodes, don't return an empty coordinate system unless it's a reset
        if not state.interactive_nodes and trigger not in ['clear-canvas-btn', 'auto-place-btn']:
             return [dash.no_update]*4

        # Build Figure
        fig = go.Figure()
        
        # Draw edges
        for i, n1 in enumerate(state.interactive_nodes):
            for j, n2 in enumerate(state.interactive_nodes):
                if i >= j: continue
                dist = np.sqrt((n1['x'] - n2['x'])**2 + (n1['y'] - n2['y'])**2)
                if dist <= tx_range:
                    fig.add_trace(go.Scatter(
                        x=[n1['x'], n2['x'], None], y=[n1['y'], n2['y'], None],
                        mode='lines', line=dict(color=GRID_COLOR, width=1), opacity=0.5, hoverinfo='none'
                    ))
        
        # Draw Nodes
        for node in state.interactive_nodes:
            color = 'blue'
            is_src = str(node['id']) == str(src)
            is_dst = str(node['id']) == str(dst)
            if is_src: color = 'green'
            if is_dst: color = 'red'
            
            node_label = f"Node {node['id']}<br>{UNICODE_ICONS[node['type']]}"
            
            # If animating and at destination, show checkmark
            if is_dst and state.current_animating_path == [] and state.narration == "✅ Journey complete!":
                 node_label += " ✓"
            
            # Highlight if animating
            if state.current_animating_path and state.animating_hop_idx < len(state.current_animating_path):
                if node['id'] == state.current_animating_path[state.animating_hop_idx]:
                    color = 'yellow'
            
            fig.add_trace(go.Scatter(
                x=[node['x']], y=[node['y']],
                mode='markers+text',
                marker=dict(size=30, symbol=SYMBOLS[node['type']], color=color),
                text=[node_label],
                textposition="bottom center",
                hovertext=f"Node {node['id']} ({node['type']})<br>Range: {tx_range}m",
                hoverinfo="text"
            ))
            
        # Draw Animating Packet
        if state.current_animating_path and state.animating_hop_idx < len(state.current_animating_path):
            curr_node_id = state.current_animating_path[state.animating_hop_idx]
            curr_node = next((n for n in state.interactive_nodes if n['id'] == curr_node_id), None)
            if curr_node:
                fig.add_trace(go.Scatter(
                    x=[curr_node['x']], y=[curr_node['y']],
                    mode='markers', marker=dict(size=18, color='yellow', line=dict(width=2, color='black')),
                    hoverinfo='none'
                ))

        fig.update_layout(
            showlegend=False, margin=dict(b=0,l=0,r=0,t=0),
            xaxis=dict(range=[0, 500], showgrid=True, gridcolor=GRID_COLOR, zeroline=False),
            yaxis=dict(range=[0, 500], showgrid=True, gridcolor=GRID_COLOR, zeroline=False),
            plot_bgcolor='white', uirevision='constant'
        )
        
        options = [{'label': f"Node {n['id']} ({n['type'].upper()})", 'value': str(n['id'])} for n in state.interactive_nodes]
        return fig, options, options, state.narration

@app.callback(
    Output('interactive-animation-status', 'children'),
    [Input('start-journey-btn', 'n_clicks')],
    [State('source-dropdown', 'value'),
     State('destination-dropdown', 'value'),
     State('interactive-protocol-radio', 'value'),
     State('tx-range-slider', 'value')]
)
def start_interactive_journey(n_clicks, src, dst, protocol, tx_range):
    if not n_clicks: return ""
    if not src or not dst: return "Select both source and destination!"
    if src == dst: return "Source and Destination must be different!"
    
    with state.lock:
        # Create a temporary simulation environment based on interactive nodes
        config = SimConfig(num_nodes=len(state.interactive_nodes), area_size=500, tx_range=tx_range)
        net = WirelessNetwork(config)
        for n in state.interactive_nodes:
            net.add_node(Node(n['id'], n['x'], n['y'], config))
        net.update_links()
        
        if not net.is_connected(int(src), int(dst)):
            state.narration = f"⚠️ No path found between Node {src} and Node {dst}. Increase range!"
            return "No path found!"
            
        proto_map = {'AODV': AODV, 'OLSR': OLSR, 'CPQR': CPQR}
        engine = SimulationEngine(proto_map[protocol], config)
        engine.network = net # Use our layout
        engine.protocol = proto_map[protocol](net, config)
        
        pkt = Packet(src=int(src), dst=int(dst), created_at=0.0)
        # Mock a delivery to get the path
        curr = int(src)
        path = [curr]
        while curr != int(dst) and len(path) < 20:
            nxt = engine.protocol.get_next_hop(curr, pkt)
            if nxt == -1: break
            path.append(nxt)
            curr = nxt
            
        if path[-1] != int(dst):
             state.narration = "Protocol failed to find destination."
             return "Journey failed!"
             
        state.current_animating_path = path
        state.animating_hop_idx = 0
        state.narration = f"📦 Packet journey started from Node {src} using {protocol}..."
        return f"Animating journey: {' -> '.join(map(str, path))}"

# --- ANIMATION ENGINE CALLBACK ---

@app.callback(
    [Output('animation-status', 'children')],
    [Input('animation-interval', 'n_intervals')]
)
def handle_animations(n):
    with state.lock:
        if not state.current_animating_path:
            # Check for new routes to animate
            if state.completed_routes:
                route = state.completed_routes.pop(0)
                state.current_animating_path = route['path']
                state.animating_hop_idx = 0
                state.animating_packet_id = route['packet_id']
                state.narration = f"📦 Animating Packet {route['packet_id']} ({route['protocol']})"
            return [dash.no_update]

        # Advance one hop
        state.animating_hop_idx += 1
        
        if state.animating_hop_idx >= len(state.current_animating_path):
            state.current_animating_path = []
            state.animating_hop_idx = 0
            state.narration = "✅ Journey complete!"
            return ["Animation complete."]
            
        curr_node = state.current_animating_path[state.animating_hop_idx]
        state.narration = f"➡️ Packet at Node {curr_node}..."
        return [f"Animating: {' -> '.join(map(str, state.current_animating_path[:state.animating_hop_idx+1]))}"]

# --- ORIGINAL RESEARCH MODE CALLBACKS (UPDATED) ---

@app.callback(
    [Output('topology-graph', 'figure'), 
     Output('metrics-chart', 'figure'), 
     Output('early-pdr-display', 'children'),
     Output('throughput-chart', 'figure'),
     Output('q-stats-display', 'children'),
     Output('status-banner', 'children'), 
     Output('q-table-panel', 'style')],
    [Input('interval-component', 'n_intervals')],
    [State('main-tabs', 'value')]
)
def update_research_charts(n, active_tab):
    if active_tab != 'research':
        return [dash.no_update]*7

    with state.lock:
        nodes = state.topology.get('nodes', [])
        if not nodes:
            return [dash.no_update]*7
            
        edge_traces = []
        for edge in state.topology.get('edges', []):
            src = next((n for n in nodes if n['id'] == edge['source']), None)
            tgt = next((n for n in nodes if n['id'] == edge['target']), None)
            if not src or not tgt: continue
            
            # Color-coding based on queue depth
            max_q = max(edge['src_queue_pct'], edge['tgt_queue_pct'])
            color = "#00FF88" # Healthy
            if max_q > 0.7: color = "#FF4444" # Red
            elif max_q > 0.3: color = "#FFA500" # Orange
            
            # Predicted lifetime check
            line_style = dict(width=1, color=color)
            if edge['llt'] < 5.0:
                line_style['dash'] = 'dot'
                line_style['color'] = '#FF0000'
                
            edge_traces.append(go.Scatter(
                x=[src['x'], tgt['x'], None], y=[src['y'], tgt['y'], None],
                line=line_style, hoverinfo='none', mode='lines', opacity=0.6
            ))
        
        # Node Trace
        node_x, node_y, node_text, node_color, node_symbols = [], [], [], [], []
        for n in nodes:
            node_x.append(n['x'])
            node_y.append(n['y'])
            
            # Status icon
            status_icon = "🟢"
            if n['queue_depth_pct'] > 0.8: status_icon = "🔴"
            elif n['queue_depth_pct'] > 0.3: status_icon = "🟡"
            
            # Highlight if animating
            is_active = False
            if state.current_animating_path and state.animating_hop_idx < len(state.current_animating_path):
                if n['id'] == state.current_animating_path[state.animating_hop_idx]:
                    is_active = True
            
            node_text.append(f"Node {n['id']}<br>{status_icon}")
            node_color.append('yellow' if is_active else CISCO_BLUE if n['energy'] > 0 else "#666")
            node_symbols.append('circle-open' if is_active else 'circle')
            
        node_trace = go.Scatter(
            x=node_x, y=node_y, mode='markers+text',
            text=node_text, textposition="bottom center",
            marker=dict(size=20, color=node_color, symbol=node_symbols, line=dict(width=1, color="white")),
            hovertext=[f"Node {n['id']}<br>Queue: {n['queue_len']} pkts ({n['queue_depth_pct']:.0%})<br>Energy: {n['energy']:.1f}" for n in nodes],
            hoverinfo="text"
        )
        
        # Highlight full path if animating
        path_traces = []
        if state.current_animating_path:
            path_x, path_y = [], []
            for hop_id in state.current_animating_path:
                node = next((n for n in nodes if n['id'] == hop_id), None)
                if node:
                    path_x.append(node['x'])
                    path_y.append(node['y'])
            path_traces.append(go.Scatter(
                x=path_x, y=path_y, mode='lines', line=dict(color='#00FF88', width=3), opacity=0.5, hoverinfo='none'
            ))
            
            # Moving Dot
            curr_idx = state.animating_hop_idx
            if curr_idx < len(state.current_animating_path):
                hop_id = state.current_animating_path[curr_idx]
                node = next((n for n in nodes if n['id'] == hop_id), None)
                if node:
                    path_traces.append(go.Scatter(
                        x=[node['x']], y=[node['y']], mode='markers',
                        marker=dict(size=18, color='yellow', line=dict(width=2, color='black')), hoverinfo='none'
                    ))

        area_size = state.config.area_size
        topo_fig = go.Figure(
            data=edge_traces + path_traces + [node_trace],
            layout=go.Layout(
                showlegend=False, margin=dict(b=0,l=0,r=0,t=0),
                xaxis=dict(range=[0, area_size], showgrid=True, gridcolor=GRID_COLOR, zeroline=False),
                yaxis=dict(range=[0, area_size], showgrid=True, gridcolor=GRID_COLOR, zeroline=False),
                plot_bgcolor='white', uirevision='constant'
            )
        )

        history = state.metrics_history
        if not history:
            metrics_fig = dash.no_update
            tput_fig = dash.no_update
            early_pdr_text = dash.no_update
        else:
            times = [m['time'] for m in history]
            metrics_fig = go.Figure()
            metrics_fig.add_trace(go.Scatter(x=times, y=[m['pdr'] for m in history], name='PDR', line=dict(color=CISCO_BLUE)))
            metrics_fig.update_layout(title="Packet Delivery Ratio", yaxis=dict(range=[0, 1.1]), margin=dict(t=30, b=30), uirevision='constant')

            tput_fig = go.Figure()
            tput_fig.add_trace(go.Scatter(x=times, y=[m['throughput_bps']/1000 for m in history], fill='tozeroy', name='kbps', line=dict(color="#28a745")))
            tput_fig.update_layout(title="Throughput (kbps)", margin=dict(t=30, b=30), uirevision='constant')
            
            early_pdr_text = f"Early PDR (first 60s): {state.early_pdr:.2%}" if state.early_pdr > 0 else "Early PDR (first 60s): N/A"
        
        q_info = f"Avg Q: {state.q_stats['mean']:.2f} | Range: {state.q_stats['min']:.2f}-{state.q_stats['max']:.2f}"
        
        status = html.Span("● LIVE", style={'color': '#28a745'}) if not state.finished and nodes else html.Span("■ IDLE", style={'color': '#666'})
        if state.finished: status = html.Span("✓ COMPLETE", style={'color': CISCO_BLUE})
        q_style = {'display': 'block'} if state.protocol_name == 'CPQR' else {'display': 'none'}
        
        return topo_fig, metrics_fig, early_pdr_text, tput_fig, q_info, status, q_style

@app.callback(
    [Output('cpqr-intelligence-status', 'children'),
     Output('reward-chart', 'figure')],
    [Input('interval-component-slow', 'n_intervals')]
)
def update_cpqr_status(n):
    with state.lock:
        if state.protocol_name != 'CPQR':
            return dash.no_update, dash.no_update
            
        status_table = html.Table([
            html.Tr([html.Th("Metric"), html.Th("Value")]),
            html.Tr([html.Td("ε_explore"), html.Td(f"{state.epsilon:.4f}")]),
            html.Tr([html.Td("Q-Guided Mode"), html.Td(f"{state.q_guided_pct:.1f}%")]),
            html.Tr([html.Td("Proactive Reroutes"), html.Td(f"{state.proactive_reroutes}")]),
            html.Tr([html.Td("Congestion Events"), html.Td(f"{state.congestion_events}")])
        ], style={'width': '100%', 'border': '1px solid #ccc', 'textAlign': 'left'})
        
        rc = state.reward_components
        count = rc.get('count', 1)
        if count == 0: count = 1
        
        reward_fig = go.Figure(data=[
            go.Bar(name='Delay', x=['Reward Components'], y=[rc.get('delay', 0) / count]),
            go.Bar(name='Congestion', x=['Reward Components'], y=[rc.get('congestion', 0) / count]),
            go.Bar(name='Link Lifetime', x=['Reward Components'], y=[rc.get('link', 0) / count]),
            go.Bar(name='Energy', x=['Reward Components'], y=[rc.get('energy', 0) / count])
        ])
        reward_fig.update_layout(barmode='stack', title="Avg Reward Components", margin=dict(t=30, b=30))
        return status_table, reward_fig

def run_simulation(protocol_name, n_nodes, speed, load, duration):
    print(f"DEBUG: run_simulation started for {protocol_name}")
    try:
        protocol_map = {'AODV': AODV, 'OLSR': OLSR, 'CPQR': CPQR}
        config = SimConfig(num_nodes=n_nodes, max_speed=speed, packet_rate=load, duration=duration, seed=42)
        
        print(f"DEBUG: Creating SimulationEngine...")
        engine = SimulationEngine(protocol_map[protocol_name], config, RandomWaypointMobility)
        engine.on_snapshot_cb = lambda t, snap: update_metrics(engine)
        engine.on_step_cb = lambda t: update_topology(engine)
        
        with state.lock:
            state.finished = False
            state.metrics_history = []
            state.topology = {'nodes': [], 'edges': [], 'packets': []}
            state.current_time = 0.0
            state.config = config
            
        print(f"DEBUG: engine.run(real_time=True) called")
        engine.run(real_time=True)
        print(f"DEBUG: engine.run finished")
    except Exception as e:
        print(f"ERROR in run_simulation: {e}")
        import traceback
        traceback.print_exc()
        
    with state.lock: state.finished = True

@app.callback(
    Output('protocol-info', 'children'),
    Input('restart-btn', 'n_clicks'),
    [State('protocol-dropdown', 'value'),
     State('nodes-slider', 'value'),
     State('speed-slider', 'value'),
     State('load-slider', 'value'),
     State('duration-input', 'value')]
)
def restart_sim(n_clicks, protocol, nodes, speed, load, duration):
    print(f"DEBUG: restart_sim triggered (clicks: {n_clicks})")
    if n_clicks is None:
        return "Select parameters and press START SIMULATION"
    global current_sim_thread
    if current_sim_thread and current_sim_thread.is_alive():
        print("DEBUG: Simulation already in progress")
        return "Simulation in progress..."
    
    print(f"DEBUG: Starting new simulation thread for {protocol}")
    current_sim_thread = threading.Thread(
        target=run_simulation, 
        args=(protocol, nodes, speed, load, float(duration)), 
        daemon=True
    )
    current_sim_thread.start()
    return f"Initializing {protocol} with {nodes} nodes..."

def run_dashboard(port=8050):
    app.run(debug=False, port=port)

if __name__ == '__main__':
    run_dashboard()