# SOMRN Frontend — React Dashboard

A real-time research dashboard for the **Self-Optimising Mesh Routing Network (SOMRN)** project. Built with React 19 + Vite, it connects to the Flask simulation backend and visualises all six routing protocols.

## Stack

| Technology | Version | Purpose |
|---|---|---|
| React | 19 | UI framework |
| Vite | 8 | Dev server + bundler |
| Vanilla CSS | — | Design system (no Tailwind) |
| Inter / JetBrains Mono | Google Fonts | Typography |

No charting library — all charts are pure SVG with cubic Bézier curves.

---

## Quick Start

```bash
# Install dependencies
npm install

# Start dev server (auto-proxies /api → localhost:5000)
npm run dev

# Open http://localhost:5173
```

The dashboard works **without the backend** — it falls back to a built-in JavaScript simulation engine and loads pre-computed CSVs from `public/results/`.

With the backend running (`cd ../mesh_routing && python server.py`), the top bar shows **LIVE** and streams real simulation data.

---

## Project Structure

```
frontend/
├── public/
│   └── results/              # Pre-computed CSV files served as static assets
│       ├── aodv_5.0_42.csv
│       ├── olsr_5.0_42.csv
│       └── cpqr_5.0_42.csv
└── src/
    ├── App.jsx               # Root — mode/scenario/protocol switching, nav bar
    ├── index.css             # CSS custom properties, animations, global styles
    ├── main.jsx              # React entry point
    ├── hooks/
    │   ├── useBackend.js     # Polls Flask /api/state; loads CSVs as fallback
    │   └── useLocalSim.js    # Browser simulation engine (all 6 protocols)
    └── components/
        ├── TopologyCanvas.jsx  # Animated SVG network canvas
        ├── UIComponents.jsx    # MetricCard, StatBar, EventFeed
        ├── ResultsChart.jsx    # SVG line chart for CSV analytics
        └── Panels.jsx          # IntroScreen, StoryMode, SingleMode, CompareMode, ResultsPanel
```

---

## Dashboard Modes

| Mode | Description |
|---|---|
| **📖 Overview** | Animated topology + live event feed + plain-English metrics table |
| **📡 Live Sim** | All 6 protocol buttons, real-time metrics, node/link legend |
| **↔ Compare** | Side-by-side AODV vs CPQR live simulations with improvement % |
| **📊 Analytics** | Multi-protocol line charts from CSV results (PDR, Delay, Throughput, Breaks) |

---

## Protocols Supported

| Button | Protocol | Colour |
|---|---|---|
| AODV | Ad hoc On-Demand Distance Vector | 🔴 `#ef4444` |
| OLSR | Optimised Link State Routing | 🔵 `#3b82f6` |
| CPQR | Congestion-Predictive Q-Routing | 🟢 `#10b981` |
| Q-RTE | Q-Routing | 🟣 `#a78bfa` |
| PQR | Predictive Q-Routing | 🟡 `#f59e0b` |
| DRL | Deep Reinforcement Learning | 🩵 `#06b6d4` |

---

## Backend API (proxied via Vite)

| Endpoint | Description |
|---|---|
| `GET /api/status` | Check if simulation is running |
| `POST /api/start` | Start sim `{ protocol, scenario, nodes, flows }` |
| `POST /api/stop` | Stop current simulation |
| `GET /api/state` | Live topology + metrics + event feed |
| `POST /api/chaos` | Trigger network stress event |
| `GET /api/results` | Pre-computed CSV results as JSON |

---

## Updating CSV Results

After running new simulations from the CLI:

```bash
cd ../mesh_routing
python main.py --protocol all --scenario earthquake
cp results/*.csv ../frontend/public/results/
```

The Analytics tab will pick up the new files automatically on next page load.

---

## Build for Production

```bash
npm run build
# Output in dist/ — can be served from any static host or Flask's static folder
```
