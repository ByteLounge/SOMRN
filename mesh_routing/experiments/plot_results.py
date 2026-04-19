import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import os

def plot_results():
    if not os.path.exists("results/all_results.csv"):
        print("No results file found. Run run_batch.py first.")
        return
        
    df = pd.DataFrame(pd.read_csv("results/all_results.csv"))
    sns.set_theme(style="whitegrid")
    
    # Figure 1: PDR vs Speed
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="speed", y="pdr", hue="protocol", marker="o")
    plt.title("Packet Delivery Ratio (PDR) vs. Node Speed")
    plt.xlabel("Max Speed (m/s)")
    plt.ylabel("PDR")
    plt.savefig("results/pdr_vs_speed.pdf")
    plt.savefig("results/pdr_vs_speed.png", dpi=300)
    
    # Figure 2: Delay vs Speed
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="speed", y="avg_delay", hue="protocol", marker="s")
    plt.title("Average End-to-End Delay vs. Node Speed")
    plt.xlabel("Max Speed (m/s)")
    plt.ylabel("Avg Delay (s)")
    plt.savefig("results/delay_vs_speed.pdf")
    plt.savefig("results/delay_vs_speed.png", dpi=300)
    
    # Figure 3: PDR vs Load
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="load", y="pdr", hue="protocol", marker="D")
    plt.title("PDR vs. Traffic Load")
    plt.xlabel("Packet Rate (pkts/s)")
    plt.ylabel("PDR")
    plt.savefig("results/pdr_vs_load.pdf")
    
    # Figure 4: Control Overhead vs Speed
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=df, x="speed", y="control_overhead", hue="protocol", marker="v")
    plt.title("Control Overhead vs. Node Speed")
    plt.xlabel("Max Speed (m/s)")
    plt.ylabel("Control Bytes")
    plt.savefig("results/overhead_vs_speed.pdf")

    # Generate Summary Table (LaTeX)
    summary = df.groupby(['protocol', 'speed']).agg({
        'pdr': ['mean', 'std'],
        'avg_delay': ['mean', 'std']
    }).round(3)
    
    with open("results/summary_table.tex", "w") as f:
        f.write(summary.to_latex())
        
    print("Plots and summary table generated in results/ directory.")

if __name__ == "__main__":
    plot_results()
