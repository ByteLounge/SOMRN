import { useState } from "react";
import { useBackendSim } from "./hooks/useBackend.js";
import { useLocalSim } from "./hooks/useLocalSim.js";
import { IntroScreen, StoryMode, SingleMode, CompareMode, ResultsPanel } from "./components/Panels.jsx";
import "./index.css";

const SCENARIOS = {
  earthquake: { name: "Earthquake Response", emoji: "🆘", color: "#ef4444", tagline: "Emergency responders in crisis zones" },
  campus:     { name: "Campus Mesh",         emoji: "🎓", color: "#3b82f6", tagline: "Students moving between buildings" },
  drone:      { name: "Drone Swarm",         emoji: "🚁", color: "#10b981", tagline: "Drones coordinating a search mission" },
};

const MODES = [
  { id: "story",   label: "📖 Overview" },
  { id: "single",  label: "📡 Live Sim" },
  { id: "compare", label: "↔ Compare" },
  { id: "results", label: "📊 Analytics" },
];

const PROTOCOLS = ["AODV", "OLSR", "CPQR"];

export default function App() {
  const [mode, setMode]         = useState("story");
  const [scenario, setScenario] = useState("earthquake");
  const [protocol, setProtocol] = useState("CPQR");
  const [running, setRunning]   = useState(false);
  const [showIntro, setShowIntro] = useState(true);
  const [chaosActive, setChaosActive] = useState(false);
  const [compareOn, setCompareOn] = useState(false);

  // Backend connection
  const { status, liveState, results, error, startSim, stopSim, triggerChaos, refreshResults } = useBackendSim();

  // Local sim (fallback / always runs for visualization)
  const localFrame     = useLocalSim(scenario, protocol,    running && mode !== "compare");
  const localFrameAodv = useLocalSim(scenario, "AODV",      compareOn);
  const localFrameCpqr = useLocalSim(scenario, "CPQR",      compareOn);

  // Merge backend live state into frame shape if available
  const mergedFrame = liveState && status.running ? {
    nodes:   liveState.topology?.nodes   ?? localFrame?.nodes   ?? [],
    links:   liveState.topology?.links   ?? localFrame?.links   ?? [],
    packets: liveState.topology?.packets ?? localFrame?.packets ?? [],
    metrics: {
      delivered:   liveState.metrics?.delivered   ?? 0,
      dropped:     liveState.metrics?.dropped      ?? 0,
      total:       liveState.metrics?.total        ?? 0,
      delay:       liveState.metrics?.delay        ?? 0,
      breaks:      liveState.metrics?.breaks       ?? 0,
      predictions: liveState.metrics?.predictions  ?? 0,
      pdr:         liveState.metrics?.pdr          ?? 0,
      avgDelay:    liveState.metrics?.delay        ?? 0,
    },
    events:  liveState.events ?? [],
    t:       liveState.time   ?? 0,
  } : localFrame;

  const backendEvents = liveState?.events ?? [];
  const meta = SCENARIOS[scenario];

  // ── Handlers ─────────────────────────────────────────────────────────────
  const handleStart = () => {
    setRunning(true);
    setShowIntro(false);
    if (status.connected) {
      startSim({ protocol: protocol.toLowerCase(), scenario, nodes: 30, flows: 5 });
    }
  };

  const handleStop = () => {
    setRunning(false);
    if (status.connected) stopSim();
  };

  const handleMode = (m) => {
    setMode(m);
    setShowIntro(false);
    if (m === "compare") { setCompareOn(true); setRunning(false); if (status.connected) stopSim(); }
    else { setCompareOn(false); setRunning(true); }
    if (m === "results") { setRunning(false); refreshResults(); }
  };

  const handleScenario = (s) => {
    setScenario(s);
    setChaosActive(false);
  };

  const handleChaos = () => {
    setChaosActive(true);
    if (status.connected) triggerChaos();
  };

  const handleProtocol = (p) => {
    setProtocol(p);
    if (status.connected && running) {
      stopSim();
      setTimeout(() => startSim({ protocol: p.toLowerCase(), scenario, nodes: 30, flows: 5 }), 300);
    }
  };

  // ── Styles ────────────────────────────────────────────────────────────────
  const topBar = {
    background: "rgba(5,5,15,0.92)", backdropFilter: "blur(28px)",
    borderBottom: "1px solid rgba(255,255,255,0.06)",
    padding: "10px 22px", display: "flex", alignItems: "center",
    gap: 14, flexWrap: "wrap", position: "sticky", top: 0, zIndex: 100,
  };

  const modeBtn = (active) => ({
    padding: "6px 14px", borderRadius: 8, border: "none", cursor: "pointer",
    fontSize: 12, fontWeight: 700, transition: "all 0.2s",
    background: active ? meta.color : "rgba(255,255,255,0.05)",
    color: active ? (meta.color === "#3b82f6" ? "#fff" : "#000") : "#64748b",
  });

  const chipBtn = (active) => ({
    padding: "5px 13px", borderRadius: 20, cursor: "pointer", fontSize: 12, fontWeight: 600,
    border: `1px solid ${active ? meta.color : "rgba(255,255,255,0.07)"}`,
    background: active ? `${meta.color}1a` : "transparent",
    color: active ? meta.color : "#475569", transition: "all 0.2s",
  });

  // ── Intro ─────────────────────────────────────────────────────────────────
  if (showIntro) return (
    <div style={{ minHeight: "100vh", background: "#05050f", fontFamily: "'Inter','Segoe UI',sans-serif",
      color: "#e2e8f0", display: "flex", flexDirection: "column" }} className="bg-animated">
      <div style={topBar}>
        <div style={{ fontSize: 14, fontWeight: 800, color: "#8b5cf6", letterSpacing: -0.3, whiteSpace: "nowrap" }}>
          🌐 SOMRN Dashboard
        </div>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ width: 7, height: 7, borderRadius: "50%", background: status.connected ? "#10b981" : "#ef4444" }}/>
          <span style={{ fontSize: 11, color: status.connected ? "#10b981" : "#64748b", fontWeight: 600 }}>
            {status.connected ? "Backend Connected" : "Offline Mode"}
          </span>
        </div>
      </div>
      <IntroScreen scenario={scenario} setScenario={handleScenario} onStart={handleStart} />
    </div>
  );

  // ── Main Dashboard ────────────────────────────────────────────────────────
  return (
    <div style={{ minHeight: "100vh", background: "#05050f", fontFamily: "'Inter','Segoe UI',sans-serif",
      color: "#e2e8f0", display: "flex", flexDirection: "column" }} className="bg-animated">

      {/* Top Bar */}
      <div style={topBar}>
        {/* Logo */}
        <button onClick={() => setShowIntro(true)} style={{ background: "none", border: "none", cursor: "pointer",
          fontSize: 14, fontWeight: 800, color: meta.color, letterSpacing: -0.3, whiteSpace: "nowrap", padding: 0 }}>
          🌐 SOMRN
        </button>

        {/* Mode tabs */}
        <div style={{ display: "flex", gap: 3, background: "rgba(255,255,255,0.04)", borderRadius: 10, padding: 3 }}>
          {MODES.map(m => (
            <button key={m.id} style={modeBtn(mode === m.id)} onClick={() => handleMode(m.id)}>{m.label}</button>
          ))}
        </div>

        {/* Scenarios */}
        <div style={{ display: "flex", gap: 5 }}>
          {Object.entries(SCENARIOS).map(([k, v]) => (
            <button key={k} style={chipBtn(scenario === k)} onClick={() => handleScenario(k)}>
              {v.emoji} {v.name.split(" ")[0]}
            </button>
          ))}
        </div>

        {/* Protocol selector (single/story mode) */}
        {(mode === "single" || mode === "story") && (
          <div style={{ display: "flex", gap: 3, background: "rgba(255,255,255,0.04)", borderRadius: 8, padding: 3 }}>
            {PROTOCOLS.map(p => (
              <button key={p} style={modeBtn(protocol === p)} onClick={() => handleProtocol(p)}>{p}</button>
            ))}
          </div>
        )}

        {/* Right controls */}
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          {/* Connection indicator */}
          <div style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 10px",
            background: "rgba(255,255,255,0.04)", borderRadius: 20,
            border: `1px solid ${status.connected ? "rgba(16,185,129,0.3)" : "rgba(255,255,255,0.07)"}` }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%",
              background: status.connected ? "#10b981" : "#475569",
              animation: status.connected && status.running ? "liveDot 1.2s ease-in-out infinite" : "none" }}/>
            <span style={{ fontSize: 10, color: status.connected ? "#10b981" : "#475569", fontWeight: 700 }}>
              {status.connected ? (status.running ? "LIVE" : "READY") : "LOCAL"}
            </span>
          </div>

          {/* Chaos button */}
          {mode !== "results" && (
            <button onClick={handleChaos} style={{
              padding: "6px 14px", borderRadius: 8, fontSize: 11, fontWeight: 700,
              border: `1px solid ${chaosActive ? "#ef4444" : "rgba(239,68,68,0.3)"}`,
              background: chaosActive ? "rgba(239,68,68,0.15)" : "transparent",
              color: chaosActive ? "#ef4444" : "#475569", transition: "all 0.2s",
            }}>⚡ {chaosActive ? "STRESS ON" : "Stress Test"}</button>
          )}

          {/* Play/Stop */}
          {mode !== "compare" && mode !== "results" && (
            <button onClick={running ? handleStop : () => setRunning(true)} style={{
              padding: "6px 14px", borderRadius: 8, fontSize: 11, fontWeight: 700,
              background: running ? "rgba(239,68,68,0.15)" : `${meta.color}22`,
              border: `1px solid ${running ? "#ef4444" : meta.color}44`,
              color: running ? "#ef4444" : meta.color, transition: "all 0.2s",
            }}>{running ? "⏹ Stop" : "▶ Start"}</button>
          )}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div style={{ background: "rgba(239,68,68,0.1)", borderBottom: "1px solid rgba(239,68,68,0.2)",
          padding: "8px 24px", fontSize: 12, color: "#fca5a5", display: "flex", alignItems: "center", gap: 8 }}>
          ⚠️ {error} — running in local simulation mode
        </div>
      )}

      {/* Scenario banner */}
      <div style={{ padding: "8px 22px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 16px",
          background: `${meta.color}0d`, borderRadius: 10, border: `1px solid ${meta.color}28` }}>
          <span style={{ fontSize: 20 }}>{meta.emoji}</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: meta.color }}>{meta.name}</div>
            <div style={{ fontSize: 11, color: "#475569" }}>{meta.tagline}</div>
          </div>
          {mode !== "compare" && mode !== "results" && (
            <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 16 }}>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 10, color: "#334155", fontWeight: 700, textTransform: "uppercase" }}>Protocol</div>
                <div style={{ fontSize: 14, fontWeight: 800, fontFamily: "'JetBrains Mono',monospace", color: meta.color }}>{protocol}</div>
              </div>
              <div style={{ textAlign: "right" }}>
                <div style={{ fontSize: 10, color: "#334155", fontWeight: 700, textTransform: "uppercase" }}>PDR</div>
                <div style={{ fontSize: 14, fontWeight: 800, fontFamily: "'JetBrains Mono',monospace",
                  color: (mergedFrame?.metrics?.pdr ?? 0) > 0.7 ? "#10b981" : "#ef4444" }}>
                  {Math.round((mergedFrame?.metrics?.pdr ?? 0) * 100)}%
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main content */}
      <div style={{ flex: 1, padding: "0 22px 22px", display: "flex", flexDirection: "column", gap: 14 }}>
        {mode === "story"   && <StoryMode frame={mergedFrame} scenario={scenario} protocol={protocol} backendEvents={backendEvents} />}
        {mode === "single"  && <SingleMode frame={mergedFrame} scenario={scenario} protocol={protocol} backendEvents={backendEvents} />}
        {mode === "compare" && <CompareMode frameAodv={localFrameAodv} frameCpqr={localFrameCpqr} scenario={scenario} />}
        {mode === "results" && <ResultsPanel results={results} />}
      </div>

      {/* Footer */}
      <div style={{ borderTop: "1px solid rgba(255,255,255,0.05)", padding: "10px 22px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        fontSize: 10, color: "#1e293b" }}>
        <span>Self-Optimizing Mesh Routing Network (SOMRN) · FYP Dashboard</span>
        <span style={{ fontFamily: "'JetBrains Mono',monospace" }}>
          {status.connected ? `Backend: localhost:5000` : "Offline — Local Simulation"}
        </span>
      </div>
    </div>
  );
}
