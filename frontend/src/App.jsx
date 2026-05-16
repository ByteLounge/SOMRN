import { useState, useEffect, useRef, useCallback } from "react";

// --- API Constants ---
const API_BASE = "http://localhost:5000/api";

// --- Bridge Simulation Hook ---
function useSimulation(scenario, protocol, running, mode, numNodes, numFlows) {
  const [frame, setFrame] = useState(null);
  const pollingRef = useRef(null);
  const lastRunningRef = useRef(false);

  // Sync Start/Stop with backend
  useEffect(() => {
    if (running && !lastRunningRef.current) {
      // Start backend simulation
      fetch(`${API_BASE}/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario, protocol, mode, nodes: numNodes, flows: numFlows })
      }).catch(err => console.error("Failed to start backend:", err));
    } else if (!running && lastRunningRef.current) {
      // Stop backend simulation
      fetch(`${API_BASE}/stop`, { method: "POST" })
        .catch(err => console.error("Failed to stop backend:", err));
    }
    lastRunningRef.current = running;
  }, [running, scenario, protocol, mode, numNodes, numFlows]);

  // Polling Loop
  useEffect(() => {
    if (!running) {
      if (pollingRef.current) clearInterval(pollingRef.current);
      return;
    }

    const fetchData = async () => {
      try {
        const res = await fetch(`${API_BASE}/state`);
        if (!res.ok) return;
        const data = await res.json();
        
        // Transform backend data to frontend format if needed
        // SimulationEngine returns {nodes: [], edges: [], packets: [], trace_path: []}
        // App expects {nodes: [], links: [], packets: [], metrics: {}, events: []}
        
        const transformedFrame = {
          nodes: data.topology.nodes.map(n => ({
            ...n,
            energy: n.energy_pct,
            dead: n.energy_pct <= 0,
            label: n.id
          })),
          links: data.topology.edges.map(e => ({
            a: data.topology.nodes.find(n => n.id === e.source),
            b: data.topology.nodes.find(n => n.id === e.target),
            quality: e.quality,
            key: `${e.source}-${e.target}`
          })),
          packets: data.topology.packets.map(p => ({
            id: p.id,
            x: p.x,
            y: p.y,
            predicted: false // Could be enhanced from backend
          })),
          tracePath: data.topology.trace_path,
          metrics: data.metrics,
          events: data.events.map((ev, i) => ({
            msg: ev.message,
            type: ev.severity === 'critical' ? 'error' : (ev.severity === 'success' ? 'success' : 'info'),
            id: i + Date.now()
          })),
          t: data.time
        };
        
        setFrame(transformedFrame);
      } catch (err) {
        console.error("Polling error:", err);
      }
    };

    pollingRef.current = setInterval(fetchData, 100); // 10 FPS polling
    return () => clearInterval(pollingRef.current);
  }, [running]);

  return frame;
}

// ─── Topology Canvas ──────────────────────────────────────────────────────────

function TopologyCanvas({ frame, protocol, scenarioMeta, compact }) {
  if (!frame) return (
    <div style={{ width: "100%", height: compact ? 220 : 420, background: "#070714",
      display: "flex", alignItems: "center", justifyContent: "center",
      borderRadius: 12, color: "#444", fontSize: 14 }}>
      Initialising...
    </div>
  );

  const W = 700, H = compact ? 220 : 420;
  // Backend uses 500x500 area, we scale to 700x420
  const scaleX = (x) => (x / 500) * W;
  const scaleY = (y) => (y / 500) * H;

  const { nodes, links, packets, tracePath } = frame;

  const nodeColor = (nd) => {
    if (nd.dead) return "#333";
    if (nd.energy > 0.6) return scenarioMeta.color;
    if (nd.energy > 0.3) return "#f59e0b";
    return "#ef4444";
  };

  const edgeColor = (q) => {
    const r = Math.round(255 * (1 - q));
    const g = Math.round(200 * q);
    return `rgba(${r},${g},80,${0.1 + q * 0.2})`; // Faint edges like user requested
  };

  return (
    <div style={{ position: "relative", width: "100%", paddingBottom: compact ? "31.4%" : "60%",
      background: "radial-gradient(ellipse at 40% 40%, #0d0d2b 0%, #070714 100%)",
      borderRadius: 12, overflow: "hidden", border: "1px solid #1a1a3e" }}>
      <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
        viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet">

        {/* Grid */}
        <defs>
          <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.03)" strokeWidth="1"/>
          </pattern>
        </defs>
        <rect width={W} height={H} fill="url(#grid)" />

        {/* Edges */}
        {links.map(l => (
          <line key={l.key}
            x1={scaleX(l.a.x)} y1={scaleY(l.a.y)} x2={scaleX(l.b.x)} y2={scaleY(l.b.y)}
            stroke={edgeColor(l.quality)} strokeWidth={1}
            strokeLinecap="round" />
        ))}

        {/* Trace Path */}
        {tracePath && tracePath.length >= 2 && (
          <polyline
            points={tracePath.map(id => {
              const n = nodes.find(nd => nd.id === id);
              return n ? `${scaleX(n.x)},${scaleY(n.y)}` : "";
            }).filter(p => p !== "").join(" ")}
            fill="none" stroke="#3498DB" strokeWidth="5"
            strokeLinejoin="round" strokeLinecap="round"
          />
        )}

        {/* Packets */}
        {packets.map(p => (
          <g key={p.id}>
             <text x={scaleX(p.x)} y={scaleY(p.y)} textAnchor="middle" fontSize={24}>✉️</text>
          </g>
        ))}

        {/* Nodes */}
        {nodes.map(nd => (
          <g key={nd.id}>
            {!nd.dead && (
              <circle cx={scaleX(nd.x)} cy={scaleY(nd.y)} r={16}
                fill={nodeColor(nd)} opacity={0.12} />
            )}
            <circle cx={scaleX(nd.x)} cy={scaleY(nd.y)} r={nd.dead ? 7 : 10}
              fill={nd.dead ? "#1a1a2e" : nodeColor(nd)}
              stroke={nd.dead ? "#333" : `${nodeColor(nd)}88`}
              strokeWidth={nd.dead ? 1 : 2} />
            <text x={scaleX(nd.x)} y={scaleY(nd.y) + 4} textAnchor="middle"
              fontSize={nd.dead ? 6 : 8} fill={nd.dead ? "#444" : "white"}
              fontFamily="monospace" fontWeight="bold">
              {nd.dead ? "✕" : scenarioMeta.nodeEmoji}
            </text>
          </g>
        ))}

        {/* Protocol label */}
        <rect x={W - 120} y={H - 30} width={110} height={22} rx={6}
          fill="rgba(52,152,219,0.2)"
          stroke="#3498DB" strokeWidth={1} />
        <text x={W - 65} y={H - 15} textAnchor="middle" fontSize={10}
          fill="#3498DB" fontFamily="monospace" fontWeight="bold">
          {protocol.toUpperCase()} ACTIVE
        </text>
      </svg>
    </div>
  );
}

// ─── Metric Card ──────────────────────────────────────────────────────────────

function MetricCard({ icon, value, label, sublabel, color, big }) {
  return (
    <div style={{
      background: "rgba(255,255,255,0.04)", borderRadius: 12,
      border: `1px solid ${color}33`, padding: big ? "18px 20px" : "14px 16px",
      display: "flex", flexDirection: "column", gap: 4, minWidth: 0,
    }}>
      <div style={{ fontSize: big ? 28 : 22, lineHeight: 1 }}>{icon}</div>
      <div style={{ fontSize: big ? 28 : 20, fontWeight: 800, color, fontFamily: "monospace", lineHeight: 1.1 }}>
        {value}
      </div>
      <div style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600, textTransform: "uppercase", letterSpacing: 0.5 }}>
        {label}
      </div>
      {sublabel && <div style={{ fontSize: 11, color: "#64748b" }}>{sublabel}</div>}
    </div>
  );
}

// ─── Event Feed ───────────────────────────────────────────────────────────────

function EventFeed({ events }) {
  const colors = {
    success: { bg: "rgba(16,185,129,0.1)", border: "#10b981", text: "#6ee7b7" },
    warning: { bg: "rgba(245,158,11,0.1)", border: "#f59e0b", text: "#fcd34d" },
    error:   { bg: "rgba(239,68,68,0.1)",  border: "#ef4444", text: "#fca5a5" },
    info:    { bg: "rgba(96,165,250,0.1)", border: "#60a5fa", text: "#93c5fd" },
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ fontSize: 11, color: "#475569", fontWeight: 700, textTransform: "uppercase",
        letterSpacing: 1, marginBottom: 2 }}>Live events</div>
      {events.length === 0 && (
        <div style={{ color: "#334155", fontSize: 12, padding: "10px 0" }}>
          Waiting for activity...
        </div>
      )}
      {[...events].reverse().slice(0, 5).map((e, i) => {
        const c = colors[e.type] || colors.info;
        return (
          <div key={e.id} style={{
            background: c.bg, border: `1px solid ${c.border}44`,
            borderLeft: `3px solid ${c.border}`,
            borderRadius: 8, padding: "8px 12px",
            fontSize: 12, color: c.text, lineHeight: 1.4,
            opacity: 1 - i * 0.15,
            transition: "all 0.3s ease",
          }}>
            {e.msg}
          </div>
        );
      })}
    </div>
  );
}

// ─── Translation Table ────────────────────────────────────────────────────────

function TranslationTable({ metrics }) {
  const pdr = metrics?.pdr ?? 0;
  const delay = metrics?.delay ?? 0;
  const breaks = metrics?.breaks ?? 0;

  const rows = [
    { metric: "Messages delivered", value: `${Math.round(pdr * 100)}%`, plain: `${Math.round(pdr * 100)} out of every 100 messages arrive`, good: pdr > 0.75 },
    { metric: "Travel time", value: `${delay.toFixed(2)}s`, plain: `Each message takes ${delay.toFixed(2)} seconds to cross the network`, good: delay < 0.5 },
    { metric: "Path disruptions", value: `${breaks}`, plain: `The route broke ${breaks} times during the simulation`, good: breaks < 10 },
    { metric: "Messages in flight", value: `${metrics?.total ?? 0}`, plain: `Total messages sent since simulation started`, good: true },
  ];

  return (
    <div style={{ background: "rgba(255,255,255,0.03)", borderRadius: 12,
      border: "1px solid #1e293b", overflow: "hidden" }}>
      <div style={{ padding: "10px 16px", background: "rgba(255,255,255,0.05)",
        fontSize: 11, fontWeight: 700, color: "#94a3b8", textTransform: "uppercase",
        letterSpacing: 1, display: "grid", gridTemplateColumns: "1fr 60px 1fr", gap: 8 }}>
        <span>What we measure</span><span>Value</span><span>What it means</span>
      </div>
      {rows.map((r, i) => (
        <div key={i} style={{
          display: "grid", gridTemplateColumns: "1fr 60px 1fr", gap: 8,
          padding: "10px 16px", alignItems: "center",
          borderTop: "1px solid #0f172a",
          background: i % 2 === 0 ? "transparent" : "rgba(255,255,255,0.01)",
        }}>
          <div style={{ fontSize: 12, color: "#94a3b8", fontWeight: 600 }}>{r.metric}</div>
          <div style={{ fontSize: 13, fontWeight: 800, fontFamily: "monospace",
            color: r.good ? "#10b981" : "#ef4444" }}>{r.value}</div>
          <div style={{ fontSize: 12, color: "#64748b" }}>{r.plain}</div>
        </div>
      ))}
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────

const SCENARIOS = {
  default:    { name: "Generic Test", emoji: "📡", nodeEmoji: "🧑", color: "#3b82f6", tagline: "Standard testing conditions" },
  earthquake: { name: "Earthquake", emoji: "🆘", nodeEmoji: "🧑", color: "#ef4444", tagline: "Emergency coordination" },
  campus:     { name: "Campus", emoji: "🎓", nodeEmoji: "📱", color: "#3b82f6", tagline: "Students on WiFi mesh" },
  drone:      { name: "Drone", emoji: "🚁", nodeEmoji: "✈", color: "#10b981", tagline: "Autonomous search mission" },
};

const PROTOCOLS = ["CPQR", "AODV", "OLSR", "Q-ROUTING", "PQR", "DRL"];

export default function App() {
  const [mode, setMode] = useState("story");
  const [scenario, setScenario] = useState("default");
  const [protocol, setProtocol] = useState("CPQR");
  const [running, setRunning] = useState(false);
  const [numNodes, setNumNodes] = useState(30);
  const [numFlows, setNumFlows] = useState(5);
  const [showIntro, setShowIntro] = useState(true);
  const [chaosActive, setChaosActive] = useState(false);

  const frame = useSimulation(scenario, protocol, running, mode, numNodes, numFlows);
  const scenarioMeta = SCENARIOS[scenario] || SCENARIOS.default;

  const toggleSim = () => setRunning(!running);
  
  const triggerChaos = () => {
    fetch(`${API_BASE}/chaos`, { method: "POST" })
      .then(() => setChaosActive(true));
  };

  const pdr = frame?.metrics?.pdr ?? 0;

  // ── Styles ──
  const S = {
    app: { minHeight: "100vh", background: "#070714", fontFamily: "IBM Plex Sans, sans-serif", color: "#e2e8f0", display: "flex", flexDirection: "column" },
    topBar: { background: "rgba(10,10,28,0.95)", backdropFilter: "blur(20px)", borderBottom: "1px solid #1e293b", padding: "12px 24px", display: "flex", alignItems: "center", gap: 16, position: "sticky", top: 0, zIndex: 100 },
    title: { fontSize: 15, fontWeight: 800, color: scenarioMeta.color, letterSpacing: -0.3, marginRight: 8, whiteSpace: "nowrap" },
    modeBtn: (active) => ({ padding: "6px 14px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 12, fontWeight: 700, background: active ? scenarioMeta.color : "rgba(255,255,255,0.06)", color: active ? "#000" : "#94a3b8" }),
    controlBtn: (active) => ({ padding: "8px 20px", borderRadius: 8, border: "none", cursor: "pointer", fontSize: 14, fontWeight: 800, background: active ? "#ef4444" : "#10b981", color: "#fff" }),
    input: { width: 60, padding: "4px 8px", borderRadius: 6, border: "1px solid #333", background: "#1a1a2e", color: "white", fontSize: 12 },
    main: { flex: 1, padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 },
    card: { background: "rgba(255,255,255,0.03)", border: "1px solid #1e293b", borderRadius: 14, padding: 20 },
  };

  if (showIntro) {
    return (
      <div style={S.app}>
        <div style={S.topBar}><div style={S.title}>🌐 SOMRN Console</div></div>
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}>
          <div style={{ maxWidth: 600, textAlign: "center" }}>
            <div style={{ fontSize: 64 }}>📡</div>
            <h1 style={{ fontSize: 32, fontWeight: 900 }}>Actual Simulation Bridge</h1>
            <p style={{ color: "#94a3b8", lineHeight: 1.6 }}>The React UI is now connected to the Python Backend. Adjust nodes and protocols, then start the simulation to see real-time data.</p>
            <button onClick={() => setShowIntro(false)} style={{ ...S.modeBtn(true), padding: "16px 40px", fontSize: 16 }}>Go to Dashboard →</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={S.app}>
      <div style={S.topBar}>
        <div style={S.title}>🌐 SOMRN Bridge</div>
        <button onClick={toggleSim} style={S.controlBtn(running)}>{running ? "⏹ Stop Sim" : "▶ Start Sim"}</button>
        
        <div style={{ display: "flex", gap: 10, alignItems: "center", borderLeft: "1px solid #333", paddingLeft: 16 }}>
           <label style={{ fontSize: 12, color: "#64748b" }}>Nodes:</label>
           <input type="number" value={numNodes} onChange={e => setNumNodes(e.target.value)} style={S.input}/>
           <label style={{ fontSize: 12, color: "#64748b" }}>Flows:</label>
           <input type="number" value={numFlows} onChange={e => setNumFlows(e.target.value)} style={S.input}/>
        </div>

        <div style={{ display: "flex", gap: 4, background: "rgba(255,255,255,0.04)", borderRadius: 10, padding: 4 }}>
          {["story", "expert"].map(m => (
            <button key={m} style={S.modeBtn(mode === m)} onClick={() => setMode(m)}>{m.toUpperCase()}</button>
          ))}
        </div>

        <select value={protocol} onChange={e => setProtocol(e.target.value)} style={{ ...S.input, width: 100 }}>
          {PROTOCOLS.map(p => <option key={p} value={p}>{p}</option>)}
        </select>

        <button style={{ ...S.modeBtn(false), border: "1px solid #ef4444", color: "#ef4444", marginLeft: "auto" }} onClick={triggerChaos}>⚡ Chaos</button>
      </div>

      <div style={S.main}>
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
          <div style={S.card}>
             <TopologyCanvas frame={frame} protocol={protocol} scenarioMeta={scenarioMeta} compact={false} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
             <div style={S.card}><EventFeed events={frame?.events ?? []} /></div>
             <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <MetricCard icon="📬" value={`${Math.round(pdr * 100)}%`} label="Delivered" color="#10b981" />
                <MetricCard icon="⚡" value={`${frame?.metrics?.breaks ?? 0}`} label="Breaks" color="#f59e0b" />
                <MetricCard icon="⏱" value={`${(frame?.metrics?.delay ?? 0).toFixed(2)}s`} label="Latency" color="#3498DB" />
                <MetricCard icon="🧠" value={`${frame?.metrics?.predictions ?? 0}`} label="Predicted" color="#a78bfa" />
             </div>
          </div>
        </div>
        <div style={S.card}><TranslationTable metrics={frame?.metrics} /></div>
      </div>
    </div>
  );
}
