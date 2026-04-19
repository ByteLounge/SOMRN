# Towards Self-Optimizing Wireless Mesh Networks: A Reinforcement Learning Approach

This project is a high-fidelity wireless mesh network simulator designed to evaluate routing protocols in dynamic, mobile environments. It features a novel Reinforcement Learning protocol, **Congestion-Predictive Q-Routing (CPQR)**, compared against classical baselines (AODV and OLSR).

## Key Features
- **Protocols**: AODV (Reactive), OLSR (Proactive), and CPQR (RL-based).
- **CPQR Novelty**: 
  - **Congestion Awareness**: Uses EWMA-smoothed queue depth predictions to avoid congested nodes.
  - **Link Lifetime Prediction**: Uses linear regression on RSSI history to avoid links likely to break soon.
- **Mobility Models**: Random Waypoint and Gauss-Markov.
- **Live Visualization**: Real-time Dash web dashboard showing topology and metrics.
- **Batch Experiments**: Automated runner for large-scale performance analysis.
- **Metrics**: PDR, Delay, Throughput, Control Overhead, and Energy consumption.

## Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Run a single simulation
```bash
python main.py --protocol cpqr --nodes 30 --speed 5.0 --live
```
- `--protocol`: aodv, olsr, or cpqr
- `--live`: Launches the Dash dashboard at `http://localhost:8050`
- `--save-video`: Generates an MP4 animation (requires ffmpeg)

### Run batch experiments
```bash
python experiments/run_batch.py
```
This will run hundreds of simulations across different speeds and loads, saving results to `results/all_results.csv`.

### Generate plots
```bash
python experiments/plot_results.py
```
Generates publication-quality figures and a LaTeX summary table in the `results/` folder.

### Run tests
```bash
pytest tests/
```

## Project Structure
- `core/`: Physical and network layer logic (Node, Link, Network, Mobility).
- `protocols/`: Routing protocol implementations.
- `metrics/`: Performance data collection and snapshotting.
- `simulation/`: Discrete-time execution engine.
- `visualization/`: Dashboard and Matplotlib animation logic.
- `experiments/`: Batch processing and plotting scripts.
