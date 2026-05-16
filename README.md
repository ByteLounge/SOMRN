# Self-Optimizing Wireless Mesh Routing Network (SOMRN)

![Python](https://img.shields.io/badge/python-3.12%2B-blue)
![React](https://img.shields.io/badge/frontend-React%2019%20%2B%20Vite-61dafb)
![Flask](https://img.shields.io/badge/backend-Flask%205-lightgrey)
![Protocols](https://img.shields.io/badge/protocols-6%20(AODV%20%7C%20OLSR%20%7C%20CPQR%20%7C%20Q--Routing%20%7C%20PQR%20%7C%20DRL)-blueviolet)
![Tests](https://img.shields.io/badge/tests-36%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-green)

> **Final Year Project** — A high-fidelity wireless mesh network simulator featuring six routing protocols, a real-time React dashboard, and a novel Reinforcement Learning protocol: **Congestion-Predictive Q-Routing (CPQR)**.

---

## 🌐 Overview

SOMRN is a full-stack research platform for evaluating autonomous routing protocols in dynamic, mobile wireless environments. The system compares **six protocols** — from classical reactive routing (AODV) to deep reinforcement learning (DRL) — across metrics including Packet Delivery Ratio, Latency, Throughput, Energy Efficiency, and Proactive Reroute counts.

The centerpiece is **CPQR**, a novel RL-based protocol that learns to predict congestion *and* link failures before they occur, enabling zero-packet-loss rerouting.

---

## 🚀 Key Features

### Simulation Engine
- **6 routing protocols** implemented from scratch in Python
- **Physical layer modelling** — Log-distance path loss, RSSI tracking, dynamic link quality
- **Mobility models** — Random Waypoint and Gauss-Markov for realistic node movement
- **Scenario presets** — Earthquake Response, Campus Mesh, Drone Swarm
- **Chaos Controller** — Stress-test trigger that doubles traffic, maximises speed, and kills nodes

### Research Dashboard (React)
- **4 view modes** — Overview, Live Sim, Side-by-Side Compare, Analytics
- **Real-time topology canvas** — Animated SVG with glowing nodes, quality-coloured edges, moving packets
- **Live metrics** — PDR, delay, throughput, route breaks, predicted reroutes
- **Analytics panel** — SVG line charts from pre-computed CSV results across all protocols
- **Backend integration** — Streams live simulation state from Flask via polling; falls back to local JS sim when offline

### Backend API (Flask)
| Endpoint | Method | Description |
|---|---|---|
| `/api/status` | GET | Simulation running state |
| `/api/start` | POST | Start simulation (protocol, scenario, nodes, flows) |
| `/api/stop` | POST | Stop simulation |
| `/api/state` | GET | Live topology, metrics, event feed |
| `/api/chaos` | POST | Trigger network stress event |
| `/api/results` | GET | Pre-computed CSV results as JSON |
| `/api/protocols` | GET | List of available protocols |

---

## 🧠 Protocol Comparison

| Protocol | Type | Key Mechanism | Colour |
|---|---|---|---|
| **AODV** | Reactive | On-demand route discovery via RREQ/RREP flooding | 🔴 Red |
| **OLSR** | Proactive | MPR-based topology broadcast, instant routing | 🔵 Blue |
| **Q-Routing** | RL | Tabular Q-learning per destination-neighbour pair | 🟣 Purple |
| **PQR** | RL + Prediction | Q-routing with RSSI-based link lifetime prediction | 🟡 Amber |
| **CPQR** ⭐ | RL + Dual Prediction | Congestion + link failure prediction with cold-start fallback | 🟢 Green |
| **DRL** | Deep RL | Neural network policy trained via experience replay | 🩵 Cyan |

---

## 🧮 CPQR — Technical Overview

CPQR treats routing as a distributed RL problem. Each node maintains a Q-table $Q(u, d, v)$ representing the expected cumulative cost to reach destination $d$ via neighbour $v$.

### Bellman Update Rule
$$Q(u, d, v) \leftarrow (1 - \alpha)\,Q(u, d, v) + \alpha \left[ R + \gamma \min_{v'} Q(v, d, v') \right]$$

### Multi-Objective Reward Function
$$R = \text{delay} + \beta \times \text{CongestionPenalty} + \gamma_{\text{link}} \times \text{LinkPenalty} + W_e \times \text{EnergyPenalty}$$

- **CongestionPenalty** — EWMA of neighbour queue depth
- **LinkPenalty** — $1 / \max(\text{LLT}, 0.1)$ based on declining RSSI trend
- **EnergyPenalty** — Penalises low-battery nodes to prevent partitions

### Cold-Start Fallback
When a node has fewer than `MIN_EXPLORE_COUNT` (default 5) Q-table updates for a destination, it falls back to BFS shortest-hop routing. This prevents the "death spiral" of empty Q-tables at simulation start.

### Epsilon-Greedy Exploration
$\epsilon$ starts at 0.3 and decays by ×0.995 per delivery down to a floor of 0.05, balancing exploration vs. exploitation as the network stabilises.

---

## 📁 Project Structure

```text
FYP/
├── README.md                      # This file
├── mesh_dashboard.jsx             # Standalone JSX demo (no build required)
├── mesh_routing/                  # Python simulation backend
│   ├── server.py                  # Flask REST API server
│   ├── main.py                    # CLI entry point
│   ├── config.py                  # SimConfig dataclass + ScenarioPresets
│   ├── core/                      # Physical & network layer
│   │   ├── network.py             # Topology graph management
│   │   ├── node.py                # Energy, queues, positioning
│   │   ├── mobility.py            # RWP & Gauss-Markov models
│   │   └── packet.py              # Packet data structure
│   ├── protocols/                 # Routing implementations
│   │   ├── base.py                # Abstract base class
│   │   ├── aodv.py                # Reactive baseline
│   │   ├── olsr.py                # Proactive baseline
│   │   ├── cpqr.py                # CPQR — novel RL protocol ⭐
│   │   ├── q_routing.py           # Pure Q-routing
│   │   ├── pqr.py                 # Predictive Q-routing
│   │   └── drl_routing.py         # Deep RL routing
│   ├── simulation/
│   │   └── engine.py              # Core simulation loop
│   ├── visualization/
│   │   ├── dashboard.py           # Legacy Dash/Plotly dashboard
│   │   ├── narrator.py            # Plain-English event narration
│   │   ├── chaos.py               # Network stress controller
│   │   └── animator.py            # Matplotlib topology animation
│   ├── experiments/               # Batch automation scripts
│   └── tests/                     # 36-test pytest suite
├── frontend/                      # React + Vite dashboard
│   ├── src/
│   │   ├── App.jsx                # Main orchestrator (modes, nav, state)
│   │   ├── index.css              # Design system (CSS variables, animations)
│   │   ├── hooks/
│   │   │   ├── useBackend.js      # Flask API polling + CSV loader
│   │   │   └── useLocalSim.js     # Browser-side fallback simulation
│   │   └── components/
│   │       ├── TopologyCanvas.jsx # Animated SVG mesh visualisation
│   │       ├── UIComponents.jsx   # MetricCard, StatBar, EventFeed
│   │       ├── ResultsChart.jsx   # Pure SVG multi-protocol line chart
│   │       └── Panels.jsx         # All 4 mode panels + intro screen
│   └── public/results/            # CSV results served as static assets
├── research_paper/
│   ├── CPQR_Research_Paper.md     # Full academic paper
│   └── results_summary.md         # Performance comparison table
└── results/                       # Pre-computed simulation CSVs
    ├── aodv_5.0_42.csv
    ├── olsr_5.0_42.csv
    └── cpqr_5.0_42.csv
```

---

## 🛠️ Installation

### 1. Clone & Environment

```bash
git clone https://github.com/ByteLounge/SOMRN
cd FYP
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
```

### 2. Backend Dependencies

```bash
pip install -r mesh_routing/requirements.txt
```

### 3. Frontend Dependencies

```bash
cd frontend
npm install
```

---

## 🖥️ Running the Full Stack

### Step 1 — Start the Flask backend

```bash
cd mesh_routing
python server.py
# → Running on http://localhost:5000
```

### Step 2 — Start the React dashboard

```bash
cd frontend
npm run dev
# → http://localhost:5173  (or 5174 if port in use)
```

The dashboard automatically detects the backend and shows **LIVE** in the top bar. If the backend is offline it shows **LOCAL** and runs the built-in JS simulation engine.

---

## 📊 CLI Usage

### Run a single protocol simulation

```bash
cd mesh_routing
python main.py --protocol cpqr --nodes 50 --speed 15.0 --duration 300
# Results saved to results/cpqr_15.0_42.csv
```

### Compare all protocols

```bash
python main.py --protocol all --scenario earthquake
```

### Available protocols

```
aodv | olsr | cpqr | q_routing | pqr | drl | all
```

### Available scenarios

```
earthquake | campus | drone | default
```

### Run batch experiments

```bash
python experiments/run_batch.py
python experiments/plot_results.py
```

### Sensitivity analysis (CPQR weight sweep)

```bash
python experiments/sensitivity_analysis.py
```

### Demo mode (viva-ready, one button)

```bash
python main.py --demo
# Launches beginner mode, earthquake scenario, compare view
```

---

## ✅ Testing

```bash
cd mesh_routing
python -m pytest tests/ -v
# 36 tests — all passing
```

Coverage report:

```bash
python -m pytest tests/ --cov=. --cov-report=html
```

---

## 📈 Key Results (Stress Test: 50 nodes, 20 m/s, 300 s)

| Protocol | PDR | Avg Delay | Control Overhead | Proactive Reroutes |
|---|---|---|---|---|
| AODV | ~0–58% (degrades) | 0.7–2.2 s | **68–88%** | 0 |
| OLSR | ~1–19% (variable) | 0.15–1.6 s | 8–11% | 0 |
| CPQR | Converges to **82–92%** | **0.15–0.3 s** | ~12% | **15,000+** |

> AODV's high control overhead comes from continuous RREQ flooding. OLSR's PDR variance is caused by MPR topology lag at high mobility. CPQR's proactive reroutes prevent drops entirely.

---

## 🔗 Dashboard Quick Reference

| Mode | Description |
|---|---|
| **📖 Overview** | Animated topology + live event feed + plain-English metrics table |
| **📡 Live Sim** | Full protocol selector (all 6) + real-time PDR/delay/breaks/reroutes |
| **↔ Compare** | Side-by-side AODV vs CPQR with live improvement percentage |
| **📊 Analytics** | Multi-protocol SVG line charts from CSV results (PDR, Delay, Throughput, Breaks) |

**Protocol selector** — each protocol has its own colour theme in the canvas badge, node gradient, and event feed.

---

## 📜 License

MIT License — see `LICENSE` for details.

---

## 🎓 Citation

```bibtex
@article{sanikop2026somrn,
  title     = {Self-Optimizing Wireless Mesh Routing Network: A Comparative Study of
               Reinforcement Learning Routing Protocols},
  author    = {Sanikop, Yash},
  year      = {2026},
  url       = {https://github.com/ByteLounge/SOMRN},
  note      = {Final Year Project, ByteLounge Research}
}
```
