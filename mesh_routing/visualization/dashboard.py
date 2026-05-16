import dash
from dash import dcc, html, callback_context
from dash.dependencies import Input, Output, State, ALL
import plotly.graph_objs as go
import threading
import time
import logging
import datetime
import os
import pandas as pd
from typing import Dict, List, Optional, Tuple
import numpy as np

from simulation.engine import SimulationEngine
from config import SimConfig, ScenarioPresets
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR
from core.mobility import RandomWaypointMobility

# New modules
from visualization.narrator import Narrator
from visualization.chaos import ChaosController
from visualization.modes import MODES, METRICS_TRANSLATIONS

logger = logging.getLogger("mesh_routing.dashboard")

class SimulationStopped(Exception):
    pass

class EngineState:
    def __init__(self):
        self.topology = {'nodes': [], 'edges': [], 'packets': []}
        self.metrics_history = []
        self.snapshot = None
        self.finished = False
        self.time = 0.0
        self.protocol_name = ""
        self.early_pdr = 0.0
        self.q_stats = {'mean': 0, 'max': 0, 'min': 0}

class DashboardState:
    def __init__(self):
        self.lock = threading.Lock()
        self.primary = EngineState()
        self.secondary = EngineState()
        
        self.primary_engine = None
        self.secondary_engine = None
        self.primary_thread = None
        self.secondary_thread = None
        self.primary_stop_event = threading.Event()
        self.secondary_stop_event = threading.Event()
        
        self.active_mode = 'expert'
        self.active_scenario = 'default'
        self.scenario_meta = None
        self.compare_mode = False
        self.intro_shown = False
        
        self.narrator = None
        self.primary_chaos = None
        self.secondary_chaos = None

    def reset_engines(self):
        self.primary_stop_event.set()
        self.secondary_stop_event.set()
        # Wait a bit for threads to notice stop event
        time.sleep(0.1)
        self.primary_stop_event.clear()
        self.secondary_stop_event.clear()
        self.primary = EngineState()
        self.secondary = EngineState()

state = DashboardState()

# STYLING
DARK_BG = "#1A1A2E"
CARD_BG = "#16213E"
GRAPH_BG = "#0F0F1A"
TEXT_COLOR = "#EAEAEA"
CONTENT_STYLE = {"padding": "20px", "paddingBottom": "80px"}

app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "SOMRN Research Console"

def get_layout():
    return html.Div([
        dcc.Store(id='active-mode', data='expert'),
        dcc.Store(id='active-scenario', data='default'),
        dcc.Store(id='compare-mode', data=False),
        dcc.Store(id='intro-hidden', data=False),
        dcc.Store(id='sim-running', data=False),
        
        # SECTION A - Top Bar
        html.Div([
            html.H2("Self-Optimizing Mesh Routing Networks", style={'margin': '0', 'flex': '1'}),
            html.Div([
                html.Div([
                    html.Label("Nodes:", style={'fontSize': '12px', 'marginRight': '5px'}),
                    dcc.Input(id='input-nodes', type='number', value=30, min=5, max=100, style={'width': '60px', 'borderRadius': '5px', 'border': '1px solid #ccc'}),
                ], style={'display': 'flex', 'alignItems': 'center'}),
                html.Div([
                    html.Label("Flows:", style={'fontSize': '12px', 'marginRight': '5px'}),
                    dcc.Input(id='input-flows', type='number', value=5, min=1, max=20, style={'width': '60px', 'borderRadius': '5px', 'border': '1px solid #ccc'}),
                ], style={'display': 'flex', 'alignItems': 'center'}),
            ], style={'display': 'flex', 'gap': '15px', 'background': 'rgba(255,255,255,0.1)', 'padding': '5px 15px', 'borderRadius': '10px'}),
            
            html.Button("▶ Start Simulation", id='btn-start-stop', style={'padding': '8px 20px', 'borderRadius': '5px', 'border': 'none', 'cursor': 'pointer', 'background': '#2ECC71', 'color': 'white', 'fontWeight': 'bold'}),

            html.Div([
                html.Button(MODES['beginner']['label'], id='btn-beginner', style={'padding': '8px 15px', 'borderRadius': '5px', 'border': 'none', 'cursor': 'pointer'}),
                html.Button(MODES['intermediate']['label'], id='btn-intermediate', style={'padding': '8px 15px', 'borderRadius': '5px', 'border': 'none', 'cursor': 'pointer'}),
                html.Button(MODES['expert']['label'], id='btn-expert', style={'padding': '8px 15px', 'borderRadius': '5px', 'border': 'none', 'cursor': 'pointer'}),
            ], style={'display': 'flex', 'gap': '10px'}),
            html.Div([
                dcc.Dropdown(
                    id='scenario-dropdown',
                    options=[
                        {'label': 'Default Scenario', 'value': 'default'},
                        {'label': 'Earthquake Response', 'value': 'earthquake'},
                        {'label': 'University Campus', 'value': 'campus'},
                        {'label': 'Drone Swarm', 'value': 'drone'}
                    ],
                    value='default',
                    style={'width': '200px', 'color': 'black'}
                ),
                html.Div(id='protocol-dropdown-container', children=[
                    dcc.Dropdown(
                        id='protocol-dropdown',
                        options=[
                            {'label': 'AODV (Reactive)', 'value': 'aodv'},
                            {'label': 'OLSR (Proactive)', 'value': 'olsr'},
                            {'label': 'CPQR (Our RL System)', 'value': 'cpqr'},
                            {'label': 'Q-Routing (Standard RL)', 'value': 'q_routing'},
                            {'label': 'PQR (Predictive Q-Routing)', 'value': 'pqr'},
                            {'label': 'DRL (Deep RL Routing)', 'value': 'drl'}
                        ],
                        value='cpqr',
                        style={'width': '200px', 'color': 'black'}
                    )
                ]),
            ], style={'display': 'flex', 'gap': '10px', 'alignItems': 'center'}),
            html.Button("↔ Compare Protocols", id='btn-compare', style={'padding': '8px 15px', 'borderRadius': '5px', 'border': 'none', 'cursor': 'pointer'}),
            html.Button("⚡ Trigger Network Stress", id='btn-chaos', style={'padding': '8px 15px', 'borderRadius': '5px', 'border': 'none', 'cursor': 'pointer', 'background': '#E74C3C', 'color': 'white', 'fontWeight': 'bold'}),
        ], style={
            'display': 'flex', 'padding': '15px 30px', 'background': CARD_BG, 
            'alignItems': 'center', 'gap': '20px', 'borderBottom': '2px solid #005a9e'
        }),

        # SECTION B - Intro Banner
        html.Div(id='intro-banner', children=[
            html.Div([
                html.H3("How does mesh routing work?"),
                html.P("Imagine you're at a concert and need to pass a note to your friend across the crowd. "
                       "You can't reach them directly, so you pass it through people between you. "
                       "Some people keep moving. Some get tired. Our system learns which people are most reliable — "
                       "and predicts who is about to move away or get too busy — before your note gets lost."),
                html.Button("Got it, show me the simulation →", id='btn-dismiss-intro', 
                            style={'padding': '15px 30px', 'background': '#005a9e', 'color': 'white', 'border': 'none', 'borderRadius': '5px', 'cursor': 'pointer', 'fontSize': '18px'})
            ], style={
                'background': 'white', 'color': 'black', 'padding': '40px', 
                'borderRadius': '15px', 'maxWidth': '700px', 'margin': '100px auto',
                'boxShadow': '0 20px 50px rgba(0,0,0,0.5)', 'textAlign': 'center'
            })
        ], style={'position': 'fixed', 'top': '0', 'left': '0', 'right': '0', 'bottom': '0', 
                  'background': 'rgba(0,0,0,0.9)', 'zIndex': '2000', 'display': 'flex'}),

        # SECTION C - Main Content
        html.Div(id='main-content', style=CONTENT_STYLE),

        # SECTION D - Metrics Translation
        html.Div(id='translation-container'),

        # SECTION E - Bottom Status Bar
        html.Div([
            html.Div(id='status-time'),
            html.Div(id='status-scenario'),
            html.Div(id='status-protocol'),
            html.Div(id='status-sim'),
            html.Button("Export metrics CSV", id='btn-export', style={'marginLeft': 'auto', 'cursor': 'pointer'})
        ], style={
            'display': 'flex', 'padding': '10px 30px', 'background': CARD_BG,
            'position': 'fixed', 'bottom': '0', 'left': '0', 'right': '0',
            'fontSize': '14px', 'gap': '30px', 'borderTop': '1px solid #333', 'zIndex': '1000'
        }),

        dcc.Interval(id='live-interval', interval=1000),
        html.Div(id='toast-container')
    ], style={'background': DARK_BG, 'color': TEXT_COLOR, 'minHeight': '100vh', 'fontFamily': 'system-ui'})

app.layout = get_layout()

# HELPER: Create Graphs
def create_topo_fig(engine_state, scenario_meta, mode):
    topo = go.Figure()
    nodes = engine_state.topology.get('nodes', [])
    edges = engine_state.topology.get('edges', [])
    
    style = MODES.get(mode, MODES['expert'])
    
    # Edges
    for e in edges:
        s_node = next((n for n in nodes if n['id'] == e['source']), None)
        t_node = next((n for n in nodes if n['id'] == e['target']), None)
        if s_node and t_node:
            quality = e.get('quality', 1.0)
            # Green (1.0) to Red (0.0)
            color = f"rgba({int(255*(1-quality))}, {int(255*quality)}, 0, 0.4)"
            topo.add_trace(go.Scatter(
                x=[s_node['x'], t_node['x'], None],
                y=[s_node['y'], t_node['y'], None],
                mode='lines',
                line=dict(color=color, width=1.5),
                hoverinfo='none'
            ))
            
    # Nodes
    if nodes:
        nx, ny, nc, nt = [], [], [], []
        for n in nodes:
            nx.append(n['x'])
            ny.append(n['y'])
            energy = n.get('energy_pct', 1.0)
            if energy > 0.6: color = '#2ECC71'
            elif energy > 0.2: color = '#F1C40F'
            elif energy > 0: color = '#E74C3C'
            else: color = '#95A5A6'
            nc.append(color)
            
            if style['topology_label_style'] == 'emoji':
                nt.append(scenario_meta['thumbnail'] if scenario_meta else "🧑")
            else:
                nt.append(str(n['id']))
                
        topo.add_trace(go.Scatter(
            x=nx, y=ny, mode='markers+text',
            marker=dict(size=18, color=nc, line=dict(width=2, color='white')),
            text=nt, textposition="middle center",
            textfont=dict(color='white', size=10)
        ))

    topo.update_layout(
        plot_bgcolor=GRAPH_BG, paper_bgcolor=GRAPH_BG,
        margin=dict(l=0,r=0,b=0,t=0),
        xaxis=dict(showgrid=False, zeroline=False, visible=False, range=[-10, 610]),
        yaxis=dict(showgrid=False, zeroline=False, visible=False, range=[-10, 610]),
        showlegend=False, uirevision='constant'
    )
    return topo

# CALLBACKS

@app.callback(
    [Output('active-mode', 'data'),
     Output('btn-beginner', 'style'),
     Output('btn-intermediate', 'style'),
     Output('btn-expert', 'style')],
    [Input('btn-beginner', 'n_clicks'),
     Input('btn-intermediate', 'n_clicks'),
     Input('btn-expert', 'n_clicks')],
    [State('active-mode', 'data')]
)
def mode_switch_callback(b, i, e, current):
    try:
        ctx = callback_context
        new_mode = current
        if ctx.triggered:
            btn_id = ctx.triggered[0]['prop_id'].split('.')[0]
            new_mode = btn_id.split('-')[1]
        
        def get_style(m):
            base = {'padding': '8px 15px', 'borderRadius': '5px', 'border': 'none', 'cursor': 'pointer'}
            if m == new_mode:
                base.update({'background': '#005a9e', 'color': 'white', 'fontWeight': 'bold'})
            else:
                base.update({'background': '#333', 'color': '#ccc'})
            return base

        return new_mode, get_style('beginner'), get_style('intermediate'), get_style('expert')
    except Exception as ex:
        logger.error(f"Error in mode_switch_callback: {ex}")
        return dash.no_update

@app.callback(
    [Output('intro-banner', 'style'),
     Output('intro-hidden', 'data')],
    [Input('btn-dismiss-intro', 'n_clicks'),
     Input('intro-hidden', 'data')],
    [State('active-mode', 'data')]
)
def dismiss_intro_callback(n, hidden, mode):
    try:
        if n or hidden:
            return {'display': 'none'}, True
        return {'position': 'fixed', 'top': '0', 'left': '0', 'right': '0', 'bottom': '0', 
                'background': 'rgba(0,0,0,0.9)', 'zIndex': '2000', 'display': 'flex'}, False
    except Exception as ex:
        logger.error(f"Error in dismiss_intro_callback: {ex}")
        return dash.no_update

@app.callback(
    [Output('compare-mode', 'data'),
     Output('btn-compare', 'style')],
    [Input('btn-compare', 'n_clicks')],
    [State('compare-mode', 'data')]
)
def compare_toggle_callback(n, current):
    try:
        new_val = current
        if n:
            new_val = not current
        style = {'padding': '8px 15px', 'borderRadius': '5px', 'border': 'none', 'cursor': 'pointer',
                 'background': '#005a9e' if new_val else '#333', 'color': 'white'}
        return new_val, style
    except Exception as ex:
        logger.error(f"Error in compare_toggle_callback: {ex}")
        return dash.no_update

@app.callback(
    [Output('active-scenario', 'data'),
     Output('btn-chaos', 'disabled'),
     Output('btn-chaos', 'children'),
     Output('protocol-dropdown-container', 'style')],
    [Input('scenario-dropdown', 'value')],
    [State('active-mode', 'data')]
)
def scenario_switch_callback(val, mode):
    try:
        proto_style = {'display': 'block'}
        if mode == 'beginner':
            proto_style = {'display': 'none'}
        return val, False, "⚡ Trigger Network Stress", proto_style
    except Exception as ex:
        logger.error(f"Error in scenario_switch_callback: {ex}")
        return dash.no_update

def run_engine_loop(engine, stop_event, side='primary'):
    last_delivered = 0
    last_dropped = 0
    last_breaks = 0
    
    try:
        def on_step(t):
            nonlocal last_delivered, last_dropped, last_breaks
            if stop_event.is_set():
                raise SimulationStopped()
            
            with state.lock:
                target = state.primary if side == 'primary' else state.secondary
                target.topology = engine.get_topology_for_dashboard()
                target.time = t
                if engine.protocol and hasattr(engine.protocol, 'get_qtable_stats'):
                    target.q_stats = engine.protocol.get_qtable_stats()
                
                if side == 'primary' and state.narrator:
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
            with state.lock:
                target = state.primary if side == 'primary' else state.secondary
                target.snapshot = snap
                target.metrics_history.append(snap)
                target.protocol_name = engine.protocol.name
                target.early_pdr = getattr(engine.metrics, 'early_pdr', 0.0)

        engine.on_step_cb = on_step
        engine.on_snapshot_cb = on_snapshot
        engine.run(real_time=True)
        
        with state.lock:
            target = state.primary if side == 'primary' else state.secondary
            target.finished = True
            
    except SimulationStopped:
        pass
    except Exception as e:
        logger.error(f"Error in engine loop {side}: {e}")

@app.callback(
    [Output('sim-running', 'data'),
     Output('btn-start-stop', 'children'),
     Output('btn-start-stop', 'style')],
    [Input('btn-start-stop', 'n_clicks')],
    [State('sim-running', 'data')]
)
def start_stop_callback(n, running):
    try:
        if not n: return running, dash.no_update, dash.no_update
        new_state = not running
        label = "▶ Start Simulation" if not new_state else "⏹ Stop Simulation"
        color = "#2ECC71" if not new_state else "#E67E22"
        style = {'padding': '8px 20px', 'borderRadius': '5px', 'border': 'none', 'cursor': 'pointer', 'background': color, 'color': 'white', 'fontWeight': 'bold'}
        
        if not new_state:
            state.reset_engines()
            
        return new_state, label, style
    except Exception as ex:
        logger.error(f"Error in start_stop_callback: {ex}")
        return dash.no_update

@app.callback(
    Output('main-content', 'children'),
    [Input('live-interval', 'n_intervals'),
     Input('active-mode', 'data'),
     Input('compare-mode', 'data'),
     Input('active-scenario', 'data'),
     Input('intro-hidden', 'data'),
     Input('sim-running', 'data'),
     Input('input-nodes', 'value'),
     Input('input-flows', 'value'),
     Input('protocol-dropdown', 'value')]
)
def update_simulation_and_ui(n, mode, compare, scenario, intro_hidden, running, num_nodes, num_flows, proto):
    try:
        if not intro_hidden: return html.Div()
        if not running:
            return html.Div([
                html.Div("Simulation Paused", style={'textAlign': 'center', 'fontSize': '24px', 'marginTop': '100px', 'opacity': '0.5'}),
                html.P("Adjust settings above and click 'Start Simulation' to begin.", style={'textAlign': 'center'})
            ])
        
        restart_needed = False
        with state.lock:
            # Check if config parameters changed
            current_nodes = state.primary_engine.config.num_nodes if state.primary_engine else None
            current_flows = state.primary_engine.config.num_flows if state.primary_engine else None
            
            # Map protocol name back to dropdown value
            p_name = state.primary.protocol_name.lower() if state.primary.protocol_name else ""
            current_proto = None
            if "aodv" in p_name: current_proto = "aodv"
            elif "olsr" in p_name: current_proto = "olsr"
            elif "cpqr" in p_name: current_proto = "cpqr"
            elif "q-routing" in p_name: current_proto = "q_routing"
            elif "pqr" in p_name: current_proto = "pqr"
            elif "drl" in p_name: current_proto = "drl"
            
            if (state.active_scenario != scenario or 
                state.compare_mode != compare or 
                current_nodes != num_nodes or 
                current_flows != num_flows or
                (current_proto and current_proto != proto)):
                
                restart_needed = True
                state.active_scenario = scenario
                state.compare_mode = compare
                
        if restart_needed:
            state.reset_engines()
            
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
                    'node_label': 'Node',
                    'packet_label': 'Message',
                    'break_label': 'Link broken',
                    'congestion_label': 'Queue building up',
                    'recovery_label': 'New route found',
                    'context_color': '#005a9e'
                }
            
            # Override with user inputs
            cfg.num_nodes = num_nodes
            cfg.num_flows = num_flows

            if mode in ['beginner', 'intermediate']:
                cfg.trace_mode = True
                cfg.packet_rate = 0.5 

            state.narrator = Narrator(state.scenario_meta)
            from protocols.q_routing import QRouting
            from protocols.pqr import PQR
            from protocols.drl_routing import DRLRouting
            p_map = {
                'aodv': AODV, 
                'olsr': OLSR, 
                'cpqr': CPQR,
                'q_routing': QRouting,
                'pqr': PQR,
                'drl': DRLRouting
            }
            
            p_cls = p_map.get(proto, CPQR)
            state.primary_engine = SimulationEngine(p_cls, cfg, RandomWaypointMobility)
            state.primary_chaos = ChaosController(state.primary_engine, state.narrator)
            state.primary_stop_event.clear()
            state.primary_thread = threading.Thread(
                target=run_engine_loop, args=(state.primary_engine, state.primary_stop_event, 'primary'),
                daemon=True
            )
            state.primary_thread.start()
            
            if compare:
                state.secondary_engine = SimulationEngine(AODV, cfg, RandomWaypointMobility)
                state.secondary_chaos = ChaosController(state.secondary_engine)
                state.secondary_stop_event.clear()
                state.secondary_thread = threading.Thread(
                    target=run_engine_loop, args=(state.secondary_engine, state.secondary_stop_event, 'secondary'),
                    daemon=True
                )
                state.secondary_thread.start()

        with state.lock:
            p_data = state.primary
            s_data = state.secondary
            meta = state.scenario_meta
            
        accent = meta['context_color']
        
        if not compare:
            return html.Div([
                html.Div([
                    html.H4(f"Topology: {meta['name']}", style={'color': accent}),
                    html.P(meta['tagline'], style={'fontStyle': 'italic', 'opacity': '0.8'}),
                    dcc.Graph(figure=create_topo_fig(p_data, meta, mode), id='main-topo')
                ], style={'flex': '0 0 65%'}),
                html.Div(id='mode-specific-right', style={'flex': '0 0 35%', 'padding': '0 20px'})
            ], style={'display': 'flex'})
        else:
            return html.Div([
                html.Div("Traditional routing REACTS after failure | Our system PREDICTS before failure", 
                         style={'textAlign': 'center', 'fontSize': '18px', 'padding': '10px', 'background': '#E74C3C', 'color': 'white', 'fontWeight': 'bold', 'borderRadius': '5px', 'marginBottom': '20px'}),
                html.Div([
                    html.Div([
                        html.H4("Traditional: AODV", style={'textAlign': 'center'}),
                        dcc.Graph(figure=create_topo_fig(s_data, meta, mode), id='secondary-topo'),
                        html.Div(id='secondary-metrics-box')
                    ], style={'flex': '1', 'background': GRAPH_BG, 'padding': '10px', 'borderRadius': '10px'}),
                    html.Div([
                        html.Div(id='headline-stat-box')
                    ], style={'width': '250px', 'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'}),
                    html.Div([
                        html.H4("Our System: CPQR", style={'textAlign': 'center', 'color': '#2ECC71'}),
                        dcc.Graph(figure=create_topo_fig(p_data, meta, mode), id='primary-topo'),
                        html.Div(id='primary-metrics-box')
                    ], style={'flex': '1', 'background': GRAPH_BG, 'padding': '10px', 'borderRadius': '10px', 'border': '2px solid #2ECC71'})
                ], style={'display': 'flex', 'gap': '10px'})
            ])
    except Exception as ex:
        logger.error(f"Error in update_simulation_and_ui: {ex}")
        return dash.no_update

@app.callback(
    [Output('mode-specific-right', 'children'),
     Output('headline-stat-box', 'children'),
     Output('status-time', 'children'),
     Output('status-scenario', 'children'),
     Output('status-protocol', 'children'),
     Output('status-sim', 'children'),
     Output('translation-container', 'children'),
     Output('secondary-metrics-box', 'children'),
     Output('primary-metrics-box', 'children')],
    [Input('live-interval', 'n_intervals')],
    [State('active-mode', 'data'),
     State('compare-mode', 'data')]
)
def live_update_callback(n, mode, compare):
    try:
        with state.lock:
            p = state.primary
            s = state.secondary
            meta = state.scenario_meta
            narrator = state.narrator
            
        if not meta: return [dash.no_update]*9
        
        style = MODES.get(mode, MODES['expert'])
        
        # 1. Right Content
        right_content = []
        if mode == 'beginner':
            feed = narrator.get_feed() if narrator else []
            right_content = html.Div([
                html.H4("What's happening?"),
                html.Div([
                    html.Div([
                        html.Span(e['icon'], style={'marginRight': '15px', 'fontSize': '20px'}),
                        html.Span(e['message'])
                    ], style={
                        'padding': '15px', 'marginBottom': '10px', 'borderRadius': '8px',
                        'background': CARD_BG, 'borderLeft': f"6px solid {c}"
                    }) for e, c in [(ev, {'success': '#2ECC71', 'warning': '#F1C40F', 'critical': '#E74C3C', 'info': '#3498DB'}.get(ev['severity'], 'grey')) for ev in feed]
                ])
            ])
        elif mode == 'intermediate':
            if p.snapshot:
                right_content = html.Div([
                    html.H4("Network Health"),
                    dcc.Graph(figure=go.Figure(go.Indicator(
                        mode="gauge+number", value=p.snapshot.pdr*100,
                        title={'text': "Messages Delivered %", 'font': {'size': 16}},
                        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#2ECC71"}}
                    )).update_layout(height=220, margin=dict(t=40,b=20), paper_bgcolor='rgba(0,0,0,0)', font={'color': 'white'})),
                    dcc.Graph(figure=go.Figure(go.Indicator(
                        mode="gauge+number", value=p.snapshot.avg_delay,
                        title={'text': "Travel Time (seconds)", 'font': {'size': 16}},
                        gauge={'axis': {'range': [0, 1]}, 'bar': {'color': "#F39C12"}}
                    )).update_layout(height=220, margin=dict(t=40,b=20), paper_bgcolor='rgba(0,0,0,0)', font={'color': 'white'}))
                ])
        else:
            if p.snapshot:
                right_content = html.Div([
                    html.H4("Technical Metrics"),
                    html.Div([
                        html.P(f"PDR: {p.snapshot.pdr:.2%}"),
                        html.P(f"Latency: {p.snapshot.avg_delay:.3f}s"),
                        html.P(f"Throughput: {p.snapshot.throughput_bps/1000:.1f} kbps"),
                        html.P(f"Overhead: {p.snapshot.control_overhead:.1%}"),
                        html.Hr(),
                        html.H5("Q-Learning Confidence"),
                        html.P(f"Avg Q-Value: {p.q_stats['mean']:.2f}")
                    ], style={'background': CARD_BG, 'padding': '20px', 'borderRadius': '10px'})
                ])

        # 2. Headline Stat
        headline = ""
        if compare and p.snapshot and s.snapshot:
            diff = (p.snapshot.pdr - s.snapshot.pdr) * 100
            headline = html.Div([
                html.Div(f"{diff:+.0f}%", style={'fontSize': '48px', 'fontWeight': 'bold'}),
                html.Div("Delivery Success vs AODV", style={'fontSize': '14px'})
            ], style={'textAlign': 'center', 'background': '#2ECC71' if diff > 0 else '#E74C3C', 'padding': '20px', 'borderRadius': '50%'})

        # Status
        time_str = f"🕒 Time: {p.time:.1f}s"
        scenario_str = f"{meta['thumbnail']} {meta['name']}"
        proto_str = f"📡 Protocol: {p.protocol_name}"
        status_str = "Status: RUNNING"
        if p.finished: status_str = "Status: ✓ COMPLETE"
        if state.primary_chaos and state.primary_chaos.triggered: status_str += " | ⚡ STRESS ACTIVE"

        # Translation Card
        trans_card = []
        if style['show_metrics_translation'] and p.snapshot:
            rows = []
            for key, trans in METRICS_TRANSLATIONS.items():
                val = getattr(p.snapshot, key, 0.0)
                rows.append(html.Tr([
                    html.Td(trans['label'], style={'fontWeight': 'bold', 'padding': '12px', 'borderBottom': '1px solid #eee'}),
                    html.Td(trans['format'](val), style={'padding': '12px', 'borderBottom': '1px solid #eee'})
                ]))
            trans_card = html.Div([
                html.H4("Metrics Decoded"),
                html.Table(rows, style={'width': '100%', 'background': 'white', 'color': '#333', 'borderRadius': '10px', 'borderCollapse': 'collapse'})
            ], style={'margin': '20px 30px'})

        # Compare metrics
        s_met = html.Div([html.P(f"PDR: {s.snapshot.pdr:.1%}")]) if compare and s.snapshot else []
        p_met = html.Div([html.P(f"PDR: {p.snapshot.pdr:.1%}")]) if compare and p.snapshot else []

        return right_content, headline, time_str, scenario_str, proto_str, status_str, trans_card, s_met, p_met
    except Exception as ex:
        logger.error(f"Error in live_update_callback: {ex}")
        return [dash.no_update]*9

@app.callback(
    [Output('btn-chaos', 'children'),
     Output('btn-chaos', 'disabled')],
    [Input('btn-chaos', 'n_clicks')],
    prevent_initial_call=True
)
def chaos_button_callback(n):
    try:
        if not n: return dash.no_update
        if state.primary_chaos: state.primary_chaos.trigger()
        if state.secondary_chaos: state.secondary_chaos.trigger()
        return "⚡ Stress Active", True
    except Exception as ex:
        logger.error(f"Error in chaos_button_callback: {ex}")
        return dash.no_update

@app.callback(
    Output('toast-container', 'children'),
    [Input('btn-export', 'n_clicks')],
    prevent_initial_call=True
)
def export_callback(n):
    try:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"results/dashboard_export_{ts}.csv"
        with state.lock:
            df = pd.DataFrame([vars(s) for s in state.primary.metrics_history])
        os.makedirs("results", exist_ok=True)
        df.to_csv(path, index=False)
        return html.Div(f"✅ Exported to {path}", style={'position': 'fixed', 'bottom': '50px', 'right': '30px', 'background': '#2ECC71', 'color': 'white', 'padding': '15px', 'borderRadius': '5px', 'zIndex': '3000'})
    except Exception as ex:
        logger.error(f"Error in export_callback: {ex}")
        return dash.no_update

def run_dashboard(port=8050, initial_mode='expert', initial_scenario='default', initial_compare=False):
    with state.lock:
        state.active_mode = initial_mode
        state.active_scenario = initial_scenario
        state.compare_mode = initial_compare
        state.intro_shown = (initial_mode != 'beginner')
            
    app.run(debug=False, port=port, host='0.0.0.0')

if __name__ == '__main__':
    run_dashboard()
