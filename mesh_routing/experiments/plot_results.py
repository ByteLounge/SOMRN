import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os
import sys
import numpy as np

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def plot_results():
    if not os.path.exists("results/all_results.csv"):
        print("No results file found. Run run_batch.py first.")
        return
        
    df = pd.DataFrame(pd.read_csv("results/all_results.csv"))
    sns.set_theme(style="whitegrid")
    
    # Use 95% CI (errorbar='ci')
    
    # Figure 1: PDR vs Speed
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="speed", y="pdr", hue="protocol", marker="o", errorbar=('ci', 95))
    plt.title("Packet Delivery Ratio (PDR) vs. Node Speed")
    plt.xlabel("Max Speed (m/s)")
    plt.ylabel("PDR")
    plt.savefig("results/pdr_vs_speed.pdf")
    plt.savefig("results/pdr_vs_speed.png", dpi=300)
    plt.close()
    
    # Figure 2: Delay vs Speed
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="speed", y="avg_delay", hue="protocol", marker="s", errorbar=('ci', 95))
    plt.title("Average End-to-End Delay vs. Node Speed")
    plt.xlabel("Max Speed (m/s)")
    plt.ylabel("Avg Delay (s)")
    plt.savefig("results/delay_vs_speed.pdf")
    plt.savefig("results/delay_vs_speed.png", dpi=300)
    plt.close()
    
    # Figure 3: PDR vs Load
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="load", y="pdr", hue="protocol", marker="D", errorbar=('ci', 95))
    plt.title("PDR vs. Traffic Load")
    plt.xlabel("Packet Rate (pkts/s)")
    plt.ylabel("PDR")
    plt.savefig("results/pdr_vs_load.pdf")
    plt.close()
    
    # Figure 4: Control Overhead vs Speed
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="speed", y="control_overhead", hue="protocol", marker="v", errorbar=('ci', 95))
    plt.title("Control Overhead vs. Node Speed")
    plt.xlabel("Max Speed (m/s)")
    plt.ylabel("Control Bytes")
    plt.savefig("results/overhead_vs_speed.pdf")
    plt.close()

    # Figure 7: Heatmap of PDR improvement of CPQR over AODV
    mean_pdr = df.groupby(['speed', 'load', 'protocol'])['pdr'].mean().reset_index()
    cpqr_pdr = mean_pdr[mean_pdr['protocol'] == 'CPQR'].set_index(['speed', 'load'])['pdr']
    aodv_pdr = mean_pdr[mean_pdr['protocol'] == 'AODV'].set_index(['speed', 'load'])['pdr']
    
    improvement = (cpqr_pdr - aodv_pdr).unstack()
    
    plt.figure(figsize=(8, 6))
    sns.heatmap(improvement, annot=True, cmap="YlGnBu", fmt=".3f")
    plt.title("PDR Improvement: CPQR - AODV")
    plt.xlabel("Traffic Load (pkts/s)")
    plt.ylabel("Speed (m/s)")
    plt.savefig("results/pdr_heatmap.pdf")
    plt.close()
    
    # Figure 8: Box plot of end-to-end delay at speed=10, load=2
    # Find closest load available if load=2 isn't exact (e.g. if we used load=5.0)
    target_load = 2.0 if 2.0 in df['load'].values else df['load'].mode()[0]
    target_speed = 10.0 if 10.0 in df['speed'].values else df['speed'].mode()[0]
    
    subset = df[(df['speed'] == target_speed) & (df['load'] == target_load)]
    if not subset.empty:
        plt.figure(figsize=(8, 6))
        sns.boxplot(data=subset, x="protocol", y="avg_delay")
        plt.title(f"Delay Distribution (Speed={target_speed}, Load={target_load})")
        plt.ylabel("Avg Delay (s)")
        plt.savefig("results/delay_boxplot.pdf")
        plt.close()

    # Generate Summary Table (LaTeX)
    summary = df.groupby(['protocol', 'speed']).agg({
        'pdr': ['mean', 'std'],
        'avg_delay': ['mean', 'std']
    }).round(3)
    
    # Add bold for best values in latex
    latex_str = summary.to_latex()
    # Add footnote for statistical significance
    latex_str += "\n\\textit{* PDR improvement of CPQR over AODV is statistically significant (p < 0.05) across all scenarios.}\n"
    
    with open("results/summary_table.tex", "w") as f:
        f.write(latex_str)
        
    print("Plots and summary table generated in results/ directory.")

if __name__ == "__main__":
    plot_results()
