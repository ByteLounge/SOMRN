import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import ScenarioPresets
from simulation.engine import SimulationEngine
from protocols.cpqr import CPQR

def run_sensitivity_analysis():
    print("Starting CPQR Weight Sensitivity Analysis...")
    
    betas = np.arange(0.1, 1.0, 0.1)
    w_es = np.arange(0.1, 1.0, 0.1)
    
    results = []
    
    total_runs = len(betas) * len(w_es)
    run_count = 0
    
    for beta in betas:
        for w_e in w_es:
            run_count += 1
            # Normalize weights if sum > 1.0 (keeping gamma fixed at 0.3 or adjusting it)
            gamma_link = 0.3
            total = beta + gamma_link + w_e
            
            b = beta
            g = gamma_link
            w = w_e
            
            if total > 1.0:
                b = beta / total
                g = gamma_link / total
                w = w_e / total
                
            print(f"Run {run_count}/{total_runs}: beta={b:.2f}, w_e={w:.2f}, gamma_link={g:.2f}")
            
            config = ScenarioPresets.stress_test()
            config.duration = 300.0
            config.beta = b
            config.gamma_link = g
            config.w_e = w
            
            engine = SimulationEngine(CPQR, config)
            metrics = engine.run()
            
            report = metrics.full_report()
            # Also extract proactive_reroutes and congestion_events from metrics if available
            # In engine, protocol is CPQR, we can access it
            pr_count = engine.protocol.proactive_reroutes_count
            ce_count = metrics.congestion_events
            
            results.append({
                'beta_raw': beta,
                'w_e_raw': w_e,
                'beta': b,
                'w_e': w,
                'gamma_link': g,
                'pdr': report['pdr'],
                'avg_delay': report['avg_delay'],
                'congestion_events': ce_count,
                'proactive_reroutes': pr_count
            })
            
    df = pd.DataFrame(results)
    
    os.makedirs("results", exist_ok=True)
    df.to_csv("results/sensitivity_matrix.csv", index=False)
    print("Results saved to results/sensitivity_matrix.csv")
    
    # Generate Heatmap
    pivot_table = df.pivot(index='w_e_raw', columns='beta_raw', values='pdr')
    # Round indices for better display
    pivot_table.index = pivot_table.index.map(lambda x: round(x, 1))
    pivot_table.columns = pivot_table.columns.map(lambda x: round(x, 1))
    pivot_table = pivot_table.sort_index(ascending=False) # y-axis from 0.9 down to 0.1
    
    plt.figure(figsize=(10, 8))
    sns.heatmap(pivot_table, annot=True, cmap="YlGnBu", fmt=".3f", cbar_kws={'label': 'Packet Delivery Ratio (PDR)'})
    plt.title('CPQR Weight Sensitivity Analysis (PDR)')
    plt.xlabel(r'Congestion Weight ($\beta$)')
    plt.ylabel(r'Energy Weight ($W_e$)')
    plt.tight_layout()
    plt.savefig("results/sensitivity_heatmap_pdr.png")
    print("Heatmap saved to results/sensitivity_heatmap_pdr.png")

if __name__ == "__main__":
    run_sensitivity_analysis()
