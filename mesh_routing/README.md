# Towards Self-Optimizing Wireless Mesh Networks

A research project comparing classical routing protocols (AODV, OLSR) with a novel Congestion-Predictive Q-Routing (CPQR) protocol in a wireless mesh network simulator.

## Installation
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Usage
Run with CPQR protocol and live dashboard:
```bash
python main.py --protocol cpqr --live
```

Run with specific scenario:
```bash
python main.py --scenario stress
```

Run batch experiments:
```bash
python experiments/run_batch.py
python experiments/plot_results.py
```

Run tests:
```bash
pytest tests/
```

## Protocols
- **AODV:** Ad hoc On-Demand Distance Vector. A reactive routing protocol that discovers routes on demand.
- **OLSR:** Optimized Link State Routing. A proactive routing protocol using multipoint relays to minimize control overhead.
- **CPQR:** Congestion-Predictive Q-Routing (Novel). A reinforcement learning-based routing protocol that predicts link lifetimes and queue congestion to make optimal, proactive routing decisions.

## Novel Contributions
- **Link Lifetime Estimation:** Uses linear regression on RSSI history to predict link failures and preemptively avoid broken routes.
- **Congestion Prediction:** Uses EWMA of queue depths combined with Q-learning to route around congested nodes.
