import argparse
import sys
import threading
import time
import os
from config import SimConfig, ScenarioPresets
from simulation.engine import SimulationEngine
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR
from visualization.dashboard import run_dashboard, update_state
from visualization.animator import TopologyAnimator
from core.mobility import RandomWaypointMobility, GaussMarkovMobility

def main():
    parser = argparse.ArgumentParser(description="Wireless Mesh Network Simulator")
    parser.add_argument("--protocol", choices=['aodv', 'olsr', 'cpqr'], default='cpqr')
    parser.add_argument("--nodes", type=int, default=30)
    parser.add_argument("--speed", type=float, default=5.0)
    parser.add_argument("--load", type=float, default=2.0)
    parser.add_argument("--duration", type=float, default=300.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--live", action="store_true", help="Launch live Dash dashboard")
    parser.add_argument("--save-video", action="store_true", help="Save animation to results/animation.mp4")
    parser.add_argument("--mobility", choices=['rwp', 'gauss'], default='rwp')
    parser.add_argument("--scenario", choices=['default', 'static', 'mobile', 'stress'], default='default')
    
    args = parser.parse_args()
    
    # 1. Load configuration
    if args.scenario == 'static':
        config = ScenarioPresets.static_low_load()
    elif args.scenario == 'mobile':
        config = ScenarioPresets.mobile_high_load()
    elif args.scenario == 'stress':
        config = ScenarioPresets.stress_test()
    else:
        config = SimConfig(
            num_nodes=args.nodes,
            max_speed=args.speed,
            packet_rate=args.load,
            duration=args.duration,
            seed=args.seed
        )
        
    protocol_map = {'aodv': AODV, 'olsr': OLSR, 'cpqr': CPQR}
    mobility_map = {'rwp': RandomWaypointMobility, 'gauss': GaussMarkovMobility}
    
    protocol_class = protocol_map[args.protocol]
    mobility_class = mobility_map[args.mobility]
    
    # 2. Setup Engine
    engine = SimulationEngine(protocol_class, config, mobility_class)
    
    # 3. Handle Live Dashboard
    if args.live:
        print("Starting live dashboard at http://localhost:8050")
        dash_thread = threading.Thread(target=run_dashboard, kwargs={'port': 8050}, daemon=True)
        dash_thread.start()
        
        # Register callback to push state to dashboard
        def on_snapshot(t, snapshot):
            update_state(engine.network, engine.metrics, t, engine.protocol.name)
        
        engine.on_snapshot_cb = on_snapshot

    # 4. Run Simulation
    print(f"Running simulation: {args.protocol.upper()} | Nodes: {config.num_nodes} | Speed: {config.max_speed}m/s")
    start_time = time.time()
    metrics = engine.run()
    end_time = time.time()
    
    # 5. Final Report
    report = metrics.full_report()
    print("\n" + "="*30)
    print("SIMULATION COMPLETE")
    print(f"Execution Time: {end_time - start_time:.2f}s")
    print("-" * 30)
    for k, v in report.items():
        print(f"{k.replace('_', ' ').title():<20}: {v:.4f}" if isinstance(v, float) else f"{k.replace('_', ' ').title():<20}: {v}")
    print("="*30 + "\n")
    
    # 6. Save results
    os.makedirs("results", exist_ok=True)
    csv_path = f"results/{args.protocol}_{args.speed}_{args.seed}.csv"
    metrics.save_csv(csv_path)
    print(f"Metrics saved to {csv_path}")
    
    # 7. Animation
    if args.save_video:
        print("Generating animation...")
        animator = TopologyAnimator(engine)
        # Note: animator needs a fresh engine or we reset the time
        # For simplicity, we just save what we have or run a shorter one
        animator.animate(duration=min(20, args.duration))
        animator.save_video("results/animation.mp4")

    if args.live:
        print("Simulation finished. Dashboard still running. Press Ctrl+C to exit.")
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            print("Exiting...")

if __name__ == "__main__":
    main()
