import argparse
import sys
import threading
import time
import os
import logging
from config import SimConfig, ScenarioPresets
from simulation.engine import SimulationEngine
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR
from visualization.dashboard import run_dashboard
from visualization.animator import TopologyAnimator
from core.mobility import RandomWaypointMobility, GaussMarkovMobility

def setup_logging(level_name: str):
    numeric_level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(level=numeric_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def main():
    parser = argparse.ArgumentParser(description="Wireless Mesh Network Simulator")
    parser.add_argument("--protocol", choices=['aodv', 'olsr', 'cpqr', 'all'], default='cpqr')
    parser.add_argument("--nodes", type=int, default=30)
    parser.add_argument("--speed", type=float, default=5.0)
    parser.add_argument("--load", type=float, default=2.0)
    parser.add_argument("--duration", type=float, default=300.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--live", action="store_true", help="Launch live Dash dashboard")
    parser.add_argument("--save-video", action="store_true", help="Save animation to results/animation.mp4")
    parser.add_argument("--mobility", choices=['rwp', 'gauss'], default='rwp')
    parser.add_argument("--scenario", choices=['default', 'static', 'mobile', 'stress', 'stress_test'], default='default')
    parser.add_argument("--log-level", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default='WARNING')
    
    args = parser.parse_args()
    setup_logging(args.log_level)
    
    if args.live:
        print("Starting live dashboard at http://localhost:8050")
        print("Use the 'START SIMULATION' button in the dashboard to begin.")
        run_dashboard(port=8050)
        return

    # CLI / Batch Mode
    if args.scenario == 'static': config = ScenarioPresets.static_low_load()
    elif args.scenario == 'mobile': config = ScenarioPresets.mobile_high_load()
    elif args.scenario in ['stress', 'stress_test']: config = ScenarioPresets.stress_test()
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
    
    protocols_to_run = ['aodv', 'olsr', 'cpqr'] if args.protocol == 'all' else [args.protocol]
    
    for proto in protocols_to_run:
        protocol_class = protocol_map[proto]
        mobility_class = mobility_map[args.mobility]
        
        # Re-initialize config for each protocol to ensure clean state
        if args.scenario == 'static': config = ScenarioPresets.static_low_load()
        elif args.scenario == 'mobile': config = ScenarioPresets.mobile_high_load()
        elif args.scenario in ['stress', 'stress_test']: config = ScenarioPresets.stress_test()
        else:
            config = SimConfig(
                num_nodes=args.nodes,
                max_speed=args.speed,
                packet_rate=args.load,
                duration=args.duration,
                seed=args.seed
            )
            
        engine = SimulationEngine(protocol_class, config, mobility_class)

        print(f"Running simulation: {proto.upper()} | Nodes: {config.num_nodes} | Speed: {config.max_speed}m/s")
        start_time = time.time()
        metrics = engine.run()
        end_time = time.time()
        
        report = metrics.full_report()
        # Add early_pdr and congestion metrics to the report manually for printing
        report['early_pdr'] = getattr(metrics, 'early_pdr', 0.0)
        report['congestion_events'] = getattr(metrics, 'congestion_events', 0)
        if proto == 'cpqr':
            report['proactive_reroutes'] = getattr(engine.protocol, 'proactive_reroutes_count', 0)

        print("\n" + "="*30)
        print("SIMULATION COMPLETE")
        print(f"Execution Time: {end_time - start_time:.2f}s")
        print("-" * 30)
        for k, v in report.items():
            print(f"{k.replace('_', ' ').title():<20}: {v:.4f}" if isinstance(v, float) else f"{k.replace('_', ' ').title():<20}: {v}")
        print("="*30 + "\n")
        
        os.makedirs("results", exist_ok=True)
        csv_path = f"results/{proto}_{args.speed}_{args.seed}.csv"
        metrics.save_csv(csv_path)
        print(f"Metrics saved to {csv_path}")
        
        if args.save_video and proto == protocols_to_run[0]: # only save for the first one if all
            print("Generating animation...")
            animator = TopologyAnimator(engine)
            animator.animate(duration=min(20, args.duration))
            animator.save_video("results/animation.mp4")

if __name__ == "__main__":
    main()
