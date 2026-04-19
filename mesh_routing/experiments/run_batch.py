import sys
import os
import multiprocessing
import pandas as pd
from pathlib import Path

# Add parent dir to path to import mesh_routing modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import SimConfig
from simulation.engine import SimulationEngine
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR
from core.mobility import RandomWaypointMobility

def run_single_experiment(args):
    proto_name, speed, load, seed = args
    
    config = SimConfig(
        max_speed=speed,
        min_speed=max(1.0, speed / 2) if speed > 0 else 0.0,
        packet_rate=load,
        seed=seed,
        duration=100.0, # Reduced for batch to save time, adjust if needed
        time_step=0.1
    )
    
    protocols = {'AODV': AODV, 'OLSR': OLSR, 'CPQR': CPQR}
    proto_class = protocols[proto_name]
    
    try:
        engine = SimulationEngine(proto_class, config, RandomWaypointMobility)
        metrics = engine.run()
        
        # Get final snapshot
        final_snap = metrics.snapshot(config.duration, window=config.duration)
        
        return {
            'Protocol': proto_name,
            'Speed': speed,
            'Load': load,
            'Seed': seed,
            'PDR': final_snap.pdr,
            'AvgDelay': final_snap.avg_delay,
            'Throughput': final_snap.throughput,
            'ControlOverhead': final_snap.control_overhead
        }
    except Exception as e:
        print(f"Error in run {args}: {e}")
        return None

if __name__ == '__main__':
    protocols = ['AODV', 'OLSR', 'CPQR']
    speeds = [0.0, 2.0, 5.0, 10.0, 20.0]
    loads = [1.0, 2.0, 5.0]
    seeds = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    
    tasks = [(p, s, l, seed) for p in protocols for s in speeds for l in loads for seed in seeds]
    total_tasks = len(tasks)
    
    print(f"Starting batch experiments. Total runs: {total_tasks}")
    
    results = []
    completed = 0
    
    # Use multiprocessing pool
    with multiprocessing.Pool(multiprocessing.cpu_count()) as pool:
        for res in pool.imap_unordered(run_single_experiment, tasks):
            completed += 1
            if res is not None:
                results.append(res)
            if completed % 10 == 0 or completed == total_tasks:
                print(f"Completed {completed}/{total_tasks}")
                
    df = pd.DataFrame(results)
    
    results_dir = Path(__file__).parent.parent / 'results'
    results_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = results_dir / 'all_results.csv'
    df.to_csv(csv_path, index=False)
    print(f"Batch experiments completed. Results saved to {csv_path}")
