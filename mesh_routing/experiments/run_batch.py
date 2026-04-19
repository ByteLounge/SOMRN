import multiprocessing
import itertools
import pandas as pd
import os
from typing import Dict, List
from config import SimConfig
from simulation.engine import SimulationEngine
from protocols.aodv import AODV
from protocols.olsr import OLSR
from protocols.cpqr import CPQR

def run_single_simulation(params: Dict) -> Dict:
    """Worker function for a single simulation run."""
    protocol_map = {"AODV": AODV, "OLSR": OLSR, "CPQR": CPQR}
    
    config = SimConfig(
        seed=params['seed'],
        max_speed=params['speed'],
        packet_rate=params['load'],
        duration=100.0, # Reduced duration for batch runs efficiency
        num_nodes=20
    )
    
    try:
        engine = SimulationEngine(protocol_map[params['protocol']], config)
        metrics = engine.run()
        report = metrics.full_report()
        
        # Add metadata
        report.update(params)
        return report
    except Exception as e:
        print(f"Error in run {params}: {e}")
        return None

def main():
    # Parameter grid
    protocols = ["AODV", "OLSR", "CPQR"]
    speeds = [0.0, 5.0, 10.0, 20.0]
    loads = [1.0, 5.0, 10.0]
    seeds = range(5) # 5 seeds per configuration
    
    combinations = list(itertools.product(protocols, speeds, loads, seeds))
    params_list = [
        {"protocol": p, "speed": s, "load": l, "seed": sd} 
        for p, s, l, sd in combinations
    ]
    
    print(f"Starting batch experiment: {len(params_list)} runs...")
    
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        results = pool.map(run_single_simulation, params_list)
        
    # Filter out failed runs
    results = [r for r in results if r is not None]
    
    df = pd.DataFrame(results)
    os.makedirs("results", exist_ok=True)
    df.to_csv("results/all_results.csv", index=False)
    print("Batch experiment complete. Results saved to results/all_results.csv")

if __name__ == "__main__":
    main()
