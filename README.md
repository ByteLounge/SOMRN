# Self-Optimizing Wireless Mesh Networks: A Reinforcement Learning Approach

![Python Version](https://img.shields.io/badge/python-3.12%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Test Status](https://img.shields.io/badge/tests-36%20passing-brightgreen)
![UI](https://img.shields.io/badge/UI-Cisco%20Packet%20Tracer%20Style-orange)

## 🌐 Overview

This project is a high-fidelity Wireless Mesh Network (WMN) simulator developed to research and evaluate autonomous routing protocols in dynamic, mobile environments. The centerpiece is a novel Reinforcement Learning (RL) protocol: **Congestion-Predictive Q-Routing (CPQR)**.

The simulator provides a comprehensive framework for comparing CPQR against industry-standard protocols (**AODV** and **OLSR**) across metrics like Packet Delivery Ratio (PDR), Latency, Throughput, and Energy Efficiency.

## 🚀 Key Features

- **RL-Based Routing (CPQR):** An adaptive routing agent that learns optimal paths based on real-time network feedback (delay, congestion, and link stability).
- **Cisco-Inspired Dashboard:** A professional-grade live visualization suite that mirrors the look and feel of Cisco Packet Tracer, allowing real-time topology management and metrics tracking.
- **Physical Layer Modeling:** Simplified path-loss models (Friis/Log-distance), RSSI tracking, and dynamic link quality estimation.
- **Mobility Models:** Dynamic node movement using Random Waypoint and Gauss-Markov models.
- **Batch Experimentation:** Automated tools for running hundreds of simulations across various seeds, node counts, and speeds to generate statistical results.

## 🖥️ Live Dashboard (Packet Tracer Mode)

The simulator includes a high-performance web dashboard built with Dash and Plotly.

**Capabilities:**
- **Dynamic Configuration:** Adjust Node Count (10-100), Speed (0-30m/s), and Traffic Load via sidebar sliders.
- **Logic Topology View:** Real-time rendering of nodes, active links (color-coded by quality), and individual packet transmissions.
- **Interactive Metrics:** Live-updating charts for PDR and Throughput (kbps).
- **Q-Learning Intelligence:** Live display of RL agent convergence and Q-table ranges.

**To Launch:**
```bash
cd mesh_routing
python main.py --live
```
Access at: `http://localhost:8050`

## 🧠 Technical Protocol: CPQR

CPQR treats routing as a distributed reinforcement learning problem. Each node maintains a Q-table $Q(u, d, v)$ representing the expected "cost" (cumulative delay) to reach destination $d$ via neighbor $v$.

### 1. Update Rule (Bellman Equation)
When a packet reaches its destination, the feedback is propagated back (or calculated locally based on in-flight tracking) to update the source node's intelligence:
$$Q(u, d, v) \leftarrow (1 - \alpha) Q(u, d, v) + \alpha \left[ R + \gamma \min_{v'} Q(v, d, v') \right]$$

### 2. Multi-Objective Reward Function
The reward $R$ is designed to minimize latency while preserving network health:
$$R = \text{delay} + \beta \times \text{CongestionPenalty} + W_e \times \text{EnergyCost}$$
- **CongestionPenalty:** Calculated using an EWMA of the neighbor's queue depth.
- **EnergyCost:** Penalizes nodes with low battery to prevent route partitions.

### 3. Mobility Resilience
CPQR utilizes **Predicted Link Lifetime (LLT)**. If a link is predicted to break within a certain threshold (based on declining RSSI trends), the agent automatically begins exploring alternative "safer" neighbors.

## 📁 Project Structure

```text
FYP/
├── README.md               # Detailed documentation
└── mesh_routing/           # Root of the application
    ├── main.py             # Entry point (Live or CLI mode)
    ├── config.py           # Simulation parameters & presets
    ├── core/               # Physical & Network layer logic
    │   ├── network.py      # Topology and link management
    │   ├── node.py         # Energy, queues, and positioning
    │   └── packet.py       # Data structure for network traffic
    ├── protocols/          # Routing implementations
    │   ├── cpqr.py         # RL-based protocol (Novel)
    │   ├── aodv.py         # Reactive baseline
    │   └── olsr.py         # Proactive baseline
    ├── simulation/         # Core execution engine
    │   └── engine.py       # Orchestrates mobility and packet flow
    ├── visualization/      # UI components
    │   └── dashboard.py    # Cisco-style live dashboard
    └── tests/              # Comprehensive test suite
```

## 🛠️ Installation

1. **Clone & Environment:**
   ```bash
   git clone <repo-url>
   cd FYP
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```
2. **Dependencies:**
   ```bash
   pip install -r mesh_routing/requirements.txt
   ```

## 📊 Usage Guide

### Scenario 1: Live Interactive Research
Launch the dashboard to manually stress-test protocols:
```bash
python mesh_routing/main.py --live
```

### Scenario 2: Headless Comparison (CLI)
Run a specific configuration and get a summary report:
```bash
python mesh_routing/main.py --protocol cpqr --nodes 50 --speed 15.0 --duration 600
```

### Scenario 3: Batch Analysis
Run the automated experiment pipeline:
```bash
python mesh_routing/experiments/run_batch.py
python mesh_routing/experiments/plot_results.py
```

### Scenario 4: Stress Test
Run a predefined stress test scenario with all protocols (50 nodes, 20m/s speed, high load):
```bash
python mesh_routing/main.py --scenario stress_test --protocol all
```

### Scenario 5: Weight Sensitivity Analysis
Perform a grid search over CPQR's reward weights (beta and W_e) to find the optimal configuration:
```bash
python mesh_routing/experiments/sensitivity_analysis.py
```

## ✅ Quality Assurance

The project maintains a rigorous testing standard. Run the full suite using:
```bash
cd mesh_routing
python -m pytest tests/ -v
```
## Dashboard

<img width="1913" height="870" alt="Screenshot 2026-04-19 214744" src="https://github.com/user-attachments/assets/b07c55e4-e260-4f5a-94f1-9ab58388cd79" />

## 📜 License
This project is licensed under the MIT License - see the LICENSE file for details.

## 🎓 Citation
If you use this simulator or the CPQR protocol in your research, please cite:
```bibtex
@article{sanikop2026cpqr,
  title={Self-Optimizing Wireless Mesh Networks: A Reinforcement Learning Approach},
  author={Yash Sanikop},
  year={2026},
  url={https://github.com/ByteLounge/SOMRN},
  publisher={Open Source Simulation}
}
```
