import multiprocessing
import itertools
import pandas as pd
import numpy as np
import os
import sys
import argparse
from typing import Dict, List

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scipy.stats import wilcoxon
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

def cohen_d(x, y):
    nx = len(x)
    ny = len(y)
    dof = nx + ny - 2
    return (np.mean(x) - np.mean(y)) / np.sqrt(((nx-1)*np.std(x, ddof=1) ** 2 + (ny-1)*np.std(y, ddof=1) ** 2) / dof)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="Run a quick validation subset")
    args = parser.parse_args()

    # Parameter grid
    protocols = ["AODV", "OLSR", "CPQR"]
    if args.quick:
        speeds = [5.0, 10.0]
        loads = [2.0, 5.0]
        seeds = range(2)
    else:
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
    
    # Statistical Rigour Tests
    print("\n--- STATISTICAL TESTS ---")
    for speed in df['speed'].unique():
        for load in df['load'].unique():
            subset = df[(df['speed'] == speed) & (df['load'] == load)]
            
            cpqr_pdr = subset[subset['protocol'] == 'CPQR']['pdr'].values
            aodv_pdr = subset[subset['protocol'] == 'AODV']['pdr'].values
            olsr_pdr = subset[subset['protocol'] == 'OLSR']['pdr'].values
            
            # Paired Wilcoxon Signed-Rank Test (requires equal length, ensure we have matching seeds if possible, 
            # here we sort by seed or assume they align if same seeds ran)
            # Actually, just use scipy.stats.wilcoxon if lengths match
            if len(cpqr_pdr) == len(aodv_pdr) and len(cpqr_pdr) > 0:
                # If differences are exactly 0 for all, wilcoxon raises ValueError, handle it.
                if np.all(cpqr_pdr == aodv_pdr):
                    p_val_aodv = 1.0
                else:
                    _, p_val_aodv = wilcoxon(cpqr_pdr, aodv_pdr)
                    
                cd_aodv = cohen_d(cpqr_pdr, aodv_pdr)
                sig_aodv = "STATISTICALLY SIGNIFICANT improvement" if p_val_aodv < 0.05 and np.mean(cpqr_pdr) > np.mean(aodv_pdr) else "No significant improvement"
                print(f"[Speed {speed}, Load {load}] CPQR vs AODV: p-value={p_val_aodv:.4f}, Cohen's d={cd_aodv:.4f} -> {sig_aodv}")

            if len(cpqr_pdr) == len(olsr_pdr) and len(cpqr_pdr) > 0:
                if np.all(cpqr_pdr == olsr_pdr):
                    p_val_olsr = 1.0
                else:
                    _, p_val_olsr = wilcoxon(cpqr_pdr, olsr_pdr)
                sig_olsr = "STATISTICALLY SIGNIFICANT improvement" if p_val_olsr < 0.05 and np.mean(cpqr_pdr) > np.mean(olsr_pdr) else "No significant improvement"
                print(f"[Speed {speed}, Load {load}] CPQR vs OLSR: p-value={p_val_olsr:.4f} -> {sig_olsr}")

if __name__ == "__main__":
    main()
