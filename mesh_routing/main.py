import argparse
import threading
import sys
import os
from pathlib import Path
import time

from config import SimConfig, ScenarioPresets
from simulation.engine import SimulationEngine
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR
from core.mobility import RandomWaypointMobility, GaussMarkovMobility

def main():
    parser = argparse.ArgumentParser(description="Wireless Mesh Network Simulator")
    parser.add_argument('--protocol', choices=['aodv', 'olsr', 'cpqr'], default='cpqr')
    parser.add_argument('--nodes', type=int, default=30)
    parser.add_argument('--speed', type=float, default=5.0)
    parser.add_argument('--load', type=float, default=2.0)
    parser.add_argument('--duration', type=float, default=300.0)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--live', action='store_true', help="Launch Dash dashboard")
    parser.add_argument('--save-video', action='store_true', help="Save animation to mp4")
    parser.add_argument('--mobility', choices=['rwp', 'gauss'], default='rwp')
    parser.add_argument('--scenario', choices=['default', 'static', 'mobile', 'stress'], default='default')
    
    args = parser.parse_args()
    
    # Configuration
    if args.scenario == 'static':
        config = ScenarioPresets.static_low_load()
    elif args.scenario == 'mobile':
        config = ScenarioPresets.mobile_high_load()
    elif args.scenario == 'stress':
        config = ScenarioPresets.stress_test()
    else:
        config = SimConfig()
        config.num_nodes = args.nodes
        config.max_speed = args.speed
        config.min_speed = max(1.0, args.speed / 2.0) if args.speed > 0 else 0.0
        config.packet_rate = args.load
        config.duration = args.duration
        config.seed = args.seed
        
    protocol_map = {'aodv': AODV, 'olsr': OLSR, 'cpqr': CPQR}
    proto_class = protocol_map[args.protocol]
    
    mobility_map = {'rwp': RandomWaypointMobility, 'gauss': GaussMarkovMobility}
    mob_class = mobility_map[args.mobility]
    
    engine = SimulationEngine(proto_class, config, mobility_class=mob_class)
    
    print(f"Starting simulation...")
    print(f"Protocol: {args.protocol.upper()}")
    print(f"Nodes: {config.num_nodes}, Max Speed: {config.max_speed} m/s, Load: {config.packet_rate} pkts/s")
    print(f"Duration: {config.duration}s")
    
    dash_thread = None
    if args.live:
        from visualization import dashboard
        
        def push_to_dash(t, snapshot):
            dashboard.update_state(
                engine.get_topology_for_dashboard(),
                engine.metrics.snapshots,
                t,
                args.protocol.upper()
            )
            
        engine.on_snapshot = push_to_dash
        
        # Start dash in background
        dash_thread = threading.Thread(target=dashboard.run, daemon=True)
        dash_thread.start()
        print("Dashboard available at http://localhost:8050")
        
        # Give dash time to start
        time.sleep(2)
        
    if args.save_video:
        from visualization.animator import TopologyAnimator
        animator = TopologyAnimator(engine)
        results_dir = Path(__file__).parent / 'results'
        results_dir.mkdir(parents=True, exist_ok=True)
        animator.save_video(str(results_dir / 'animation.mp4'))
        metrics = engine.metrics
    else:
        metrics = engine.run()
        
    # Final Report
    report = metrics.full_report()
    print("\n--- FINAL RESULTS ---")
    for k, v in report.items():
        if isinstance(v, float):
            print(f"{k}: {v:.4f}")
        else:
            print(f"{k}: {v}")
            
    # Save CSV
    results_dir = Path(__file__).parent / 'results'
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / f"{args.protocol}_{int(args.speed)}_{args.seed}.csv"
    metrics.save_csv(str(csv_path))
    print(f"Metrics saved to {csv_path}")
    
    if args.live and dash_thread:
        print("Simulation complete. Dashboard will remain running until you exit (Ctrl+C).")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

if __name__ == '__main__':
    main()
