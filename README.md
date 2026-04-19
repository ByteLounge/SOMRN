# Towards Self-Optimizing Wireless Mesh Networks: A Reinforcement Learning Approach

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Test Status](https://img.shields.io/badge/tests-passing-brightgreen)

This project is a high-fidelity wireless mesh network simulator designed to evaluate routing protocols in dynamic, mobile environments. It features a novel Reinforcement Learning protocol, **Congestion-Predictive Q-Routing (CPQR)**, compared against classical baselines (AODV and OLSR).

## Architecture

```text
+-------------------+       +-------------------+       +-------------------+
|    Simulation     |       |      Metrics      |       |   Visualization   |
|      Engine       |<----->|     Collector     |------>|     Dashboard     |
+-------------------+       +-------------------+       +-------------------+
        |  |                          |                           |
        |  |                          |                           |
        v  v                          v                           v
+-------------------+       +-------------------+       +-------------------+
|      Core         |       |    Protocols      |       |    Experiments    |
| (Node, Link, Net) |<----->| (AODV, OLSR, CPQR)|       |  (Batch, Plots)   |
+-------------------+       +-------------------+       +-------------------+
```

## Protocol Comparison

| Protocol | Type | Overhead | Convergence | Mobility Handling | Novelty |
|----------|------|----------|-------------|-------------------|---------|
| **AODV** | Reactive | Low | Slow | Moderate | Standard RFC |
| **OLSR** | Proactive | High | Fast | Poor | MPR Selection |
| **CPQR** | Hybrid/RL | Moderate | Fast | Excellent | Q-Learning, LLT |

## CPQR Mathematical Description

CPQR uses a Q-learning approach to find the optimal path. The Q-value $Q(u, d, v)$ represents the estimated cost (delay) from node $u$ to destination $d$ via neighbor $v$.

**Update Rule:**
When a packet is delivered, the Q-value is updated:
$$Q(u, d, v) \leftarrow (1 - \alpha) Q(u, d, v) + \alpha \left[ R + \gamma \min_{v'} Q(v, d, v') \right]$$

**Reward Function:**
The reward $R$ penalizes delay, congestion, and energy consumption:
$$R = \text{delay} + \beta \times CP + W_e \times \text{energy\_cost}$$

**Congestion Penalty (CP):**
Normalized EWMA of queue depth:
$$CP = \frac{\text{EWMA}(Queue)}{Max\_Queue\_Capacity}$$

## Installation

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

## Usage

### Run a single simulation
```bash
make run
```
Or manually:
```bash
python main.py --protocol cpqr --nodes 30 --speed 5.0 --live
```

### Run batch experiments
```bash
make batch
```

### Generate plots
```bash
make plots
```

### Run tests
```bash
make test
```

## Reproducing Figures

1. Run the batch experiments: `make batch` (This will generate `results/all_results.csv`)
2. Generate the plots: `make plots` (This will create all PDFs and PNGs in the `results/` directory)
3. Check the `results/summary_table.tex` for the LaTeX table.

## Known Limitations
- The simulation runs in discrete time steps, which can cause slight inaccuracies compared to continuous-time simulators like ns-3.
- The MAC layer is simplified (no CSMA/CA backoff simulation).

## Future Work
- Implement a continuous-time event-driven engine.
- Integrate realistic MAC layer models (e.g., 802.11).
- Add support for multiple Q-learning agents communicating directly.

## Citation

If you use this code in your research, please cite:
```bibtex
@misc{cpqr2026,
  author = {Your Name},
  title = {Towards Self-Optimizing Wireless Mesh Networks: A Reinforcement Learning Approach},
  year = {2026},
  publisher = {GitHub},
  journal = {GitHub repository}
}
```