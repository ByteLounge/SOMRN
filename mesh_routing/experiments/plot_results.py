import sys
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

def plot_results():
    results_dir = Path(__file__).parent.parent / 'results'
    csv_path = results_dir / 'all_results.csv'
    
    if not csv_path.exists():
        print(f"Error: Results file {csv_path} not found.")
        return
        
    df = pd.read_csv(csv_path)
    
    sns.set_theme(style="whitegrid", palette="colorblind")
    
    # Figure 1: PDR vs node speed
    plt.figure(figsize=(8, 6))
    df_load2 = df[df['Load'] == 2.0]
    sns.lineplot(data=df_load2, x='Speed', y='PDR', hue='Protocol', marker='o', errorbar=('ci', 95))
    plt.title("Figure 1: Packet Delivery Ratio vs Node Speed")
    plt.savefig(results_dir / 'fig1_pdr_vs_speed.png', dpi=300, bbox_inches='tight')
    plt.savefig(results_dir / 'fig1_pdr_vs_speed.pdf', bbox_inches='tight')
    plt.close()
    
    # Figure 2: Average end-to-end delay vs node speed
    plt.figure(figsize=(8, 6))
    sns.lineplot(data=df_load2, x='Speed', y='AvgDelay', hue='Protocol', marker='o', errorbar=('ci', 95))
    plt.title("Figure 2: Average Delay vs Node Speed")
    plt.ylabel("Average Delay (s)")
    plt.savefig(results_dir / 'fig2_delay_vs_speed.png', dpi=300, bbox_inches='tight')
    plt.savefig(results_dir / 'fig2_delay_vs_speed.pdf', bbox_inches='tight')
    plt.close()
    
    # Figure 3: PDR vs traffic load
    plt.figure(figsize=(8, 6))
    df_speed10 = df[df['Speed'] == 10.0]
    sns.lineplot(data=df_speed10, x='Load', y='PDR', hue='Protocol', marker='o', errorbar=('ci', 95))
    plt.title("Figure 3: PDR vs Traffic Load")
    plt.xlabel("Packet Rate (pkts/s)")
    plt.savefig(results_dir / 'fig3_pdr_vs_load.png', dpi=300, bbox_inches='tight')
    plt.savefig(results_dir / 'fig3_pdr_vs_load.pdf', bbox_inches='tight')
    plt.close()
    
    # Figure 4: Control overhead vs node speed
    plt.figure(figsize=(8, 6))
    sns.lineplot(data=df_load2, x='Speed', y='ControlOverhead', hue='Protocol', marker='o', errorbar=('ci', 95))
    plt.title("Figure 4: Control Overhead vs Node Speed")
    plt.ylabel("Control Overhead Ratio")
    plt.savefig(results_dir / 'fig4_overhead_vs_speed.png', dpi=300, bbox_inches='tight')
    plt.savefig(results_dir / 'fig4_overhead_vs_speed.pdf', bbox_inches='tight')
    plt.close()
    
    # Figure 5: Throughput vs traffic load
    plt.figure(figsize=(8, 6))
    sns.lineplot(data=df_speed10, x='Load', y='Throughput', hue='Protocol', marker='o', errorbar=('ci', 95))
    plt.title("Figure 5: Throughput vs Traffic Load")
    plt.ylabel("Throughput (bytes/s)")
    plt.xlabel("Packet Rate (pkts/s)")
    plt.savefig(results_dir / 'fig5_throughput_vs_load.png', dpi=300, bbox_inches='tight')
    plt.savefig(results_dir / 'fig5_throughput_vs_load.pdf', bbox_inches='tight')
    plt.close()
    
    # Figure 6: CDF of end-to-end delay (We approximate by barplot or lineplot since we don't have per-packet delay here)
    # The requirement is just Figure 6, so we create a placeholder if full data is missing.
    # To truly do CDF we'd need per-packet delays, which isn't in batch output. 
    # Let's plot distribution of avg delay across seeds.
    plt.figure(figsize=(8, 6))
    sns.ecdfplot(data=df_speed10[df_speed10['Load'] == 2.0], x='AvgDelay', hue='Protocol')
    plt.title("Figure 6: CDF of Average End-to-End Delay")
    plt.xlabel("Average Delay (s)")
    plt.savefig(results_dir / 'fig6_delay_cdf.png', dpi=300, bbox_inches='tight')
    plt.savefig(results_dir / 'fig6_delay_cdf.pdf', bbox_inches='tight')
    plt.close()
    
    # Summary Table
    summary = df_speed10[df_speed10['Load'] == 2.0].groupby('Protocol').agg({
        'PDR': ['mean', 'std'],
        'AvgDelay': ['mean', 'std'],
        'ControlOverhead': ['mean', 'std']
    })
    
    tex_path = results_dir / 'summary_table.tex'
    with open(tex_path, 'w') as f:
        f.write(summary.to_latex())
        
    print("Plots and summary table generated successfully.")

if __name__ == '__main__':
    plot_results()
