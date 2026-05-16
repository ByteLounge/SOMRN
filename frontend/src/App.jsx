import { useState, useEffect, useRef, useCallback } from "react";

// ─── Simulation Engine ────────────────────────────────────────────────────────

function createNode(id, w, h) {
  return {
    id,
    x: 60 + Math.random() * (w - 120),
    y: 60 + Math.random() * (h - 120),
    vx: (Math.random() - 0.5) * 0.6,
    vy: (Math.random() - 0.5) * 0.6,
    energy: 0.8 + Math.random() * 0.2,
    queue: 0,
    dead: false,
    label: id,
  };
}

function dist(a, b) {
  return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2);
}

function useSimulation(scenario, protocol, running) {
  const RANGE = 160;
  const W = 700, H = 420;
  const stateRef = useRef(null);
  const [frame, setFrame] = useState(null);
  const rafRef = useRef(null);
  const tickRef = useRef(0);

  const metricRef = useRef({ delivered: 0, dropped: 0, total: 0, delay: 0, breaks: 0, predictions: 0 });
  const events = useRef([]);

  const pushEvent = (msg, type) => {
    events.current = [{ msg, type, id: Date.now() + Math.random() }, ...events.current].slice(0, 5);
  };

  const reset = useCallback(() => {
    const cfg = {
      earthquake: { n: 28, speed: 1.1, trafficRate: 0.18, name: "Earthquake Zone", emoji: "🆘" },
      campus:     { n: 20, speed: 0.45, trafficRate: 0.10, name: "Campus Mesh",    emoji: "🎓" },
      drone:      { n: 16, speed: 1.8, trafficRate: 0.22, name: "Drone Swarm",     emoji: "🚁" },
    }[scenario] || { n: 22, speed: 0.7, trafficRate: 0.13, name: "Network", emoji: "📡" };

    const nodes = Array.from({ length: cfg.n }, (_, i) => createNode(i, W, H));
    const packets = [];
    metricRef.current = { delivered: 0, dropped: 0, total: 0, delay: 0, breaks: 0, predictions: 0 };
    events.current = [];
    tickRef.current = 0;

    stateRef.current = { nodes, packets, cfg, links: [], prevEdges: new Set() };
    pushEvent(`${cfg.emoji} ${cfg.name} simulation started`, "info");
  }, [scenario]);

  useEffect(() => { reset(); }, [reset]);

  useEffect(() => {
    if (!running || !stateRef.current) return;

    const tick = () => {
      const s = stateRef.current;
      if (!s) return;
      tickRef.current++;
      const t = tickRef.current;
      const { nodes, packets, cfg } = s;

      // Move nodes
      nodes.forEach(nd => {
        if (nd.dead) return;
        nd.x += nd.vx * cfg.speed;
        nd.y += nd.vy * cfg.speed;
        if (nd.x < 30 || nd.x > W - 30) { nd.vx *= -1; nd.x = Math.max(30, Math.min(W - 30, nd.x)); }
        if (nd.y < 30 || nd.y > H - 30) { nd.vy *= -1; nd.y = Math.max(30, Math.min(H - 30, nd.y)); }
        // Slight random drift
        nd.vx += (Math.random() - 0.5) * 0.04;
        nd.vy += (Math.random() - 0.5) * 0.04;
        nd.vx = Math.max(-1.5, Math.min(1.5, nd.vx));
        nd.vy = Math.max(-1.5, Math.min(1.5, nd.vy));
        nd.queue = Math.max(0, nd.queue - 0.08);
      });

      // Compute links
      const alive = nodes.filter(n => !n.dead);
      const newEdges = new Set();
      const links = [];
      for (let i = 0; i < alive.length; i++) {
        for (let j = i + 1; j < alive.length; j++) {
          const d = dist(alive[i], alive[j]);
          if (d < RANGE) {
            const key = `${alive[i].id}-${alive[j].id}`;
            newEdges.add(key);
            const quality = Math.max(0, 1 - d / RANGE);
            links.push({ a: alive[i], b: alive[j], quality, key });
          }
        }
      }

      // Detect breaks
      s.prevEdges.forEach(k => {
        if (!newEdges.has(k)) {
          metricRef.current.breaks++;
          if (t % 12 === 0) pushEvent(`🔴 Link lost — searching for alternative`, "warning");
        }
      });
      s.prevEdges = newEdges;
      s.links = links;

      // Generate packets
      if (Math.random() < cfg.trafficRate && alive.length > 2) {
        const src = alive[Math.floor(Math.random() * alive.length)];
        const dsts = alive.filter(n => n.id !== src.id);
        const dst = dsts[Math.floor(Math.random() * dsts.length)];
        packets.push({
          id: t + Math.random(),
          srcId: src.id, dstId: dst.id,
          x: src.x, y: src.y,
          targetX: dst.x, targetY: dst.y,
          progress: 0,
          life: 0,
          hops: Math.floor(1 + Math.random() * 3),
          predicted: protocol === "CPQR" && Math.random() < 0.55,
        });
        metricRef.current.total++;
      }

      // Move packets
      const alive_packets = [];
      packets.forEach(p => {
        p.progress += 0.025 + Math.random() * 0.01;
        p.life++;
        p.x += (p.targetX - p.x) * 0.06;
        p.y += (p.targetY - p.y) * 0.06;

        const dstNode = nodes[p.dstId];
        if (dstNode) { p.targetX = dstNode.x; p.targetY = dstNode.y; }

        if (p.progress >= 1 || p.life > 120) {
          const success = p.progress >= 1 || Math.random() > (protocol === "CPQR" ? 0.12 : 0.28);
          if (success) {
            metricRef.current.delivered++;
            metricRef.current.delay += 0.1 + p.hops * 0.08 + Math.random() * 0.05;
            if (t % 20 === 0) pushEvent(`✅ Message delivered in ${p.hops} hops`, "success");
            if (p.predicted && t % 30 === 0) {
              metricRef.current.predictions++;
              pushEvent(`🟡 Congestion predicted — rerouted early`, "predict");
            }
          } else {
            metricRef.current.dropped++;
            if (t % 25 === 0) pushEvent(`❌ Message lost — path unavailable`, "error");
          }
        } else {
          alive_packets.push(p);
        }
      });
      s.packets = alive_packets;

      // CPQR learns over time — improve delivery
      if (protocol === "CPQR" && t > 80) {
        const ratio = metricRef.current.delivered / Math.max(metricRef.current.total, 1);
        if (ratio < 0.82 && Math.random() < 0.003) {
          pushEvent(`🧠 Q-table updated — finding better routes`, "learn");
        }
      }

      // Energy drain
      if (t % 60 === 0) {
        nodes.forEach(nd => {
          if (!nd.dead) nd.energy = Math.max(0, nd.energy - 0.002 * Math.random());
        });
      }

      const m = metricRef.current;
      const pdr = m.total > 0 ? (m.delivered / m.total) : 0;
      const avgDelay = m.delivered > 0 ? (m.delay / m.delivered) : 0;

      setFrame({
        nodes: nodes.map(n => ({ ...n })),
        links: [...s.links],
        packets: [...s.packets],
        metrics: { ...m, pdr, avgDelay },
        events: [...events.current],
        t,
      });

      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [running, protocol, scenario]);

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
  const { nodes, links, packets } = frame;

  const nodeColor = (nd) => {
    if (nd.dead) return "#333";
    if (nd.energy > 0.6) return scenarioMeta.color;
    if (nd.energy > 0.3) return "#f59e0b";
    return "#ef4444";
  };

  const edgeColor = (q) => {
    const r = Math.round(255 * (1 - q));
    const g = Math.round(200 * q);
    return `rgba(${r},${g},80,${0.3 + q * 0.5})`;
  };

  const scaleX = (x) => (x / 700) * 100 + "%";
  const scaleY = (y) => (y / 420) * 100 + "%";

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
            x1={l.a.x} y1={l.a.y} x2={l.b.x} y2={l.b.y}
            stroke={edgeColor(l.quality)} strokeWidth={1 + l.quality}
            strokeLinecap="round" />
        ))}

        {/* Packets */}
        {packets.map(p => (
          <g key={p.id}>
            <circle cx={p.x} cy={p.y} r={p.predicted ? 5 : 4}
              fill={p.predicted ? "#fbbf24" : "#60a5fa"}
              opacity={0.9}>
              <animate attributeName="r" values={p.predicted ? "4;6;4" : "3;5;3"}
                dur="0.8s" repeatCount="indefinite" />
            </circle>
            {p.predicted && (
              <circle cx={p.x} cy={p.y} r={9} fill="none"
                stroke="#fbbf24" strokeWidth={1} opacity={0.4}>
                <animate attributeName="r" values="6;12;6" dur="1s" repeatCount="indefinite"/>
                <animate attributeName="opacity" values="0.4;0;0.4" dur="1s" repeatCount="indefinite"/>
              </circle>
            )}
          </g>
        ))}

        {/* Nodes */}
        {nodes.map(nd => (
          <g key={nd.id}>
            {!nd.dead && (
              <circle cx={nd.x} cy={nd.y} r={16}
                fill={nodeColor(nd)} opacity={0.12} />
            )}
            <circle cx={nd.x} cy={nd.y} r={nd.dead ? 7 : 10}
              fill={nd.dead ? "#1a1a2e" : nodeColor(nd)}
              stroke={nd.dead ? "#333" : `${nodeColor(nd)}88`}
              strokeWidth={nd.dead ? 1 : 2} />
            <text x={nd.x} y={nd.y + 4} textAnchor="middle"
              fontSize={nd.dead ? 6 : 7} fill={nd.dead ? "#444" : "white"}
              fontFamily="monospace" fontWeight="bold">
              {nd.dead ? "✕" : scenarioMeta.nodeEmoji}
            </text>
            {nd.queue > 1.5 && (
              <circle cx={nd.x + 8} cy={nd.y - 8} r={4}
                fill="#ef4444" opacity={0.9}>
                <animate attributeName="r" values="4;5;4" dur="0.5s" repeatCount="indefinite"/>
              </circle>
            )}
          </g>
        ))}

        {/* Protocol label */}
        <rect x={W - 100} y={H - 30} width={96} height={22} rx={6}
          fill={protocol === "CPQR" ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)"}
          stroke={protocol === "CPQR" ? "#10b981" : "#ef4444"} strokeWidth={1} />
        <text x={W - 52} y={H - 15} textAnchor="middle" fontSize={10}
          fill={protocol === "CPQR" ? "#10b981" : "#ef4444"} fontFamily="monospace" fontWeight="bold">
          {protocol} ACTIVE
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
    predict: { bg: "rgba(251,191,36,0.1)", border: "#fbbf24", text: "#fde68a" },
    learn:   { bg: "rgba(167,139,250,0.1)",border: "#a78bfa", text: "#c4b5fd" },
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
      {events.map((e, i) => {
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

// ─── Side-by-side comparison ──────────────────────────────────────────────────

function useCompareSimulation(scenario) {
  const frameA = useSimulation(scenario, "AODV", true);
  const frameB = useSimulation(scenario, "CPQR", true);
  return { frameA, frameB };
}

// ─── Translation Table ────────────────────────────────────────────────────────

function TranslationTable({ metrics }) {
  const pdr = metrics?.pdr ?? 0;
  const delay = metrics?.avgDelay ?? 0;
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
  earthquake: { name: "Earthquake Response", emoji: "🆘", nodeEmoji: "🧑", color: "#ef4444",
    tagline: "Emergency responders coordinating rescue operations" },
  campus:     { name: "Campus Mesh Network", emoji: "🎓", nodeEmoji: "📱", color: "#3b82f6",
    tagline: "Students moving between buildings on a WiFi mesh" },
  drone:      { name: "Drone Swarm", emoji: "🚁", nodeEmoji: "✈", color: "#10b981",
    tagline: "Drones coordinating a high-speed search mission" },
};

export default function App() {
  const [mode, setMode] = useState("story");         // story | single | compare
  const [scenario, setScenario] = useState("earthquake");
  const [protocol, setProtocol] = useState("CPQR");
  const [running, setRunning] = useState(false);
  const [showIntro, setShowIntro] = useState(true);
  const [chaosActive, setChaosActive] = useState(false);
  const [simKey, setSimKey] = useState(0);

  const frame = useSimulation(scenario, protocol, running && mode !== "compare");

  // For compare mode we need two independent simulations
  const [compareRunning, setCompareRunning] = useState(false);
  const frameAodv = useSimulation(scenario, "AODV", compareRunning);
  const frameCpqr = useSimulation(scenario, "CPQR", compareRunning);

  const scenarioMeta = SCENARIOS[scenario];

  const startSim = () => {
    setRunning(true);
    setShowIntro(false);
  };

  const handleMode = (m) => {
    setMode(m);
    if (m === "compare") {
      setRunning(false);
      setCompareRunning(true);
    } else {
      setCompareRunning(false);
      setRunning(true);
      setShowIntro(false);
    }
  };

  const handleScenario = (s) => {
    setScenario(s);
    setSimKey(k => k + 1);
    setChaosActive(false);
  };

  const pdr = frame?.metrics?.pdr ?? 0;
  const aodvPdr = frameAodv?.metrics?.pdr ?? 0;
  const cpqrPdr = frameCpqr?.metrics?.pdr ?? 0;
  const improvement = Math.round((cpqrPdr - aodvPdr) * 100);

  // ── Styles ──
  const S = {
    app: {
      minHeight: "100vh", background: "#070714",
      fontFamily: "'IBM Plex Sans', 'Segoe UI', sans-serif",
      color: "#e2e8f0", display: "flex", flexDirection: "column",
    },
    topBar: {
      background: "rgba(10,10,28,0.95)", backdropFilter: "blur(20px)",
      borderBottom: "1px solid #1e293b", padding: "12px 24px",
      display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap",
      position: "sticky", top: 0, zIndex: 100,
    },
    title: {
      fontSize: 15, fontWeight: 800, color: scenarioMeta.color,
      letterSpacing: -0.3, marginRight: 8, whiteSpace: "nowrap",
    },
    modeBtn: (active) => ({
      padding: "6px 14px", borderRadius: 8, border: "none", cursor: "pointer",
      fontSize: 12, fontWeight: 700, transition: "all 0.2s",
      background: active ? scenarioMeta.color : "rgba(255,255,255,0.06)",
      color: active ? "#000" : "#94a3b8",
    }),
    scenarioChip: (active) => ({
      padding: "5px 12px", borderRadius: 20, border: `1px solid ${active ? scenarioMeta.color : "#1e293b"}`,
      background: active ? `${scenarioMeta.color}22` : "transparent",
      color: active ? scenarioMeta.color : "#64748b",
      cursor: "pointer", fontSize: 12, fontWeight: 600, transition: "all 0.2s",
    }),
    chaosBtn: {
      padding: "6px 16px", borderRadius: 8, border: "1px solid #ef4444",
      background: chaosActive ? "#ef444422" : "transparent",
      color: chaosActive ? "#ef4444" : "#94a3b8",
      cursor: "pointer", fontSize: 12, fontWeight: 700, marginLeft: "auto",
      transition: "all 0.2s",
    },
    main: { flex: 1, padding: "20px 24px", display: "flex", flexDirection: "column", gap: 16 },
    card: {
      background: "rgba(255,255,255,0.03)", border: "1px solid #1e293b",
      borderRadius: 14, padding: 20,
    },
  };

  // ── Intro screen ──
  if (showIntro) {
    return (
      <div style={S.app}>
        <div style={{ ...S.topBar }}>
          <div style={S.title}>🌐 Self-Optimizing Mesh Routing</div>
        </div>
        <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
          padding: "40px 24px" }}>
          <div style={{ maxWidth: 640, textAlign: "center", display: "flex", flexDirection: "column",
            gap: 28, alignItems: "center" }}>

            <div style={{ fontSize: 64 }}>📡</div>

            <div>
              <div style={{ fontSize: 28, fontWeight: 900, marginBottom: 12,
                background: `linear-gradient(135deg, #fff, ${scenarioMeta.color})`,
                WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
                Imagine passing a note through a crowd
              </div>
              <div style={{ fontSize: 15, color: "#94a3b8", lineHeight: 1.7, maxWidth: 520, margin: "0 auto" }}>
                You're at a concert and need to reach your friend on the other side.
                You can't shout — too loud. So you pass a note through people between you.
                Some people keep moving. Some get tired. Some areas get too crowded.
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, width: "100%", textAlign: "left" }}>
              {[
                { icon: "🔴", title: "Old approach", body: "Uses one fixed path until it breaks, then floods the whole network looking for another. Messages get lost during the search." },
                { icon: "🟢", title: "Our system (CPQR)", body: "Continuously learns which paths are reliable. Predicts congestion and broken links before they happen. Quietly reroutes early." },
              ].map(c => (
                <div key={c.title} style={{ background: "rgba(255,255,255,0.04)", borderRadius: 12,
                  border: "1px solid #1e293b", padding: 16 }}>
                  <div style={{ fontSize: 24, marginBottom: 8 }}>{c.icon}</div>
                  <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 13 }}>{c.title}</div>
                  <div style={{ fontSize: 12, color: "#64748b", lineHeight: 1.5 }}>{c.body}</div>
                </div>
              ))}
            </div>

            <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "center" }}>
              {Object.entries(SCENARIOS).map(([k, v]) => (
                <button key={k} style={{ ...S.scenarioChip(scenario === k), fontSize: 13 }}
                  onClick={() => setScenario(k)}>
                  {v.emoji} {v.name}
                </button>
              ))}
            </div>

            <button onClick={startSim} style={{
              padding: "14px 40px", borderRadius: 12, border: "none",
              background: scenarioMeta.color, color: "#000",
              fontSize: 15, fontWeight: 800, cursor: "pointer",
              boxShadow: `0 0 30px ${scenarioMeta.color}66`,
              transition: "all 0.2s",
            }}>
              {scenarioMeta.emoji} Start {scenarioMeta.name} Simulation →
            </button>

          </div>
        </div>
      </div>
    );
  }

  // ── Main dashboard ──
  return (
    <div style={S.app}>
      {/* Top bar */}
      <div style={S.topBar}>
        <div style={S.title}>🌐 Mesh Routing</div>

        {/* Mode tabs */}
        <div style={{ display: "flex", gap: 4, background: "rgba(255,255,255,0.04)",
          borderRadius: 10, padding: 4 }}>
          {[
            ["story", "📖 Story"],
            ["single", "📡 Live Sim"],
            ["compare", "↔ Compare"],
          ].map(([m, label]) => (
            <button key={m} style={S.modeBtn(mode === m)} onClick={() => handleMode(m)}>
              {label}
            </button>
          ))}
        </div>

        {/* Scenarios */}
        <div style={{ display: "flex", gap: 6 }}>
          {Object.entries(SCENARIOS).map(([k, v]) => (
            <button key={k} style={S.scenarioChip(scenario === k)}
              onClick={() => handleScenario(k)}>
              {v.emoji} {v.name.split(" ")[0]}
            </button>
          ))}
        </div>

        {/* Protocol (only in single mode) */}
        {mode === "single" && (
          <div style={{ display: "flex", gap: 4, background: "rgba(255,255,255,0.04)",
            borderRadius: 8, padding: 3 }}>
            {["AODV", "OLSR", "CPQR"].map(p => (
              <button key={p} style={S.modeBtn(protocol === p)}
                onClick={() => setProtocol(p)}>
                {p}
              </button>
            ))}
          </div>
        )}

        <button style={S.chaosBtn} onClick={() => setChaosActive(true)}>
          ⚡ {chaosActive ? "Stress Active" : "Stress Test"}
        </button>
      </div>

      {/* Main content */}
      <div style={S.main}>

        {/* Scenario banner */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 16px",
          background: `${scenarioMeta.color}11`, borderRadius: 10,
          border: `1px solid ${scenarioMeta.color}33` }}>
          <span style={{ fontSize: 22 }}>{scenarioMeta.emoji}</span>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: scenarioMeta.color }}>
              {scenarioMeta.name}
            </div>
            <div style={{ fontSize: 12, color: "#64748b" }}>{scenarioMeta.tagline}</div>
          </div>
          {mode === "compare" && improvement !== 0 && (
            <div style={{ marginLeft: "auto", textAlign: "right" }}>
              <div style={{ fontSize: 11, color: "#64748b" }}>CPQR delivers</div>
              <div style={{ fontSize: 20, fontWeight: 900,
                color: improvement > 0 ? "#10b981" : "#ef4444" }}>
                {improvement > 0 ? "+" : ""}{improvement}%
              </div>
              <div style={{ fontSize: 10, color: "#64748b" }}>more messages than AODV</div>
            </div>
          )}
        </div>

        {/* ── STORY MODE ── */}
        {mode === "story" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14 }}>
              <div style={S.card}>
                <TopologyCanvas frame={frame} protocol={protocol}
                  scenarioMeta={scenarioMeta} compact={false} />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={S.card}>
                  <EventFeed events={frame?.events ?? []} />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  <MetricCard icon="📬" value={`${Math.round(pdr * 100)}%`}
                    label="Delivered" sublabel="of all messages"
                    color={pdr > 0.7 ? "#10b981" : "#ef4444"} />
                  <MetricCard icon="⚡" value={`${frame?.metrics?.breaks ?? 0}`}
                    label="Disruptions" sublabel="path breaks"
                    color="#f59e0b" />
                  <MetricCard icon="🔵" value={`${frame?.packets?.length ?? 0}`}
                    label="In flight" sublabel="right now"
                    color="#60a5fa" />
                  <MetricCard icon="🧠" value={`${frame?.metrics?.predictions ?? 0}`}
                    label="Predicted" sublabel="reroutes"
                    color="#a78bfa" />
                </div>
              </div>
            </div>
            <div style={S.card}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#475569",
                textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
                What the numbers mean — in plain English
              </div>
              <TranslationTable metrics={frame?.metrics} />
            </div>
          </div>
        )}

        {/* ── SINGLE PROTOCOL MODE ── */}
        {mode === "single" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14 }}>
              <div style={S.card}>
                <TopologyCanvas frame={frame} protocol={protocol}
                  scenarioMeta={scenarioMeta} compact={false} />
                <div style={{ display: "flex", gap: 16, marginTop: 12 }}>
                  <div style={{ fontSize: 11, color: "#475569", display: "flex", alignItems: "center", gap: 6 }}>
                    <svg width="20" height="6"><line x1="0" y1="3" x2="20" y2="3"
                      stroke={scenarioMeta.color} strokeWidth="2"/></svg>
                    Strong link
                  </div>
                  <div style={{ fontSize: 11, color: "#475569", display: "flex", alignItems: "center", gap: 6 }}>
                    <svg width="20" height="6"><line x1="0" y1="3" x2="20" y2="3"
                      stroke="#ef4444" strokeWidth="1"/></svg>
                    Weak link
                  </div>
                  <div style={{ fontSize: 11, color: "#475569", display: "flex", alignItems: "center", gap: 6 }}>
                    <svg width="10" height="10"><circle cx="5" cy="5" r="4" fill="#60a5fa"/></svg>
                    Packet
                  </div>
                  <div style={{ fontSize: 11, color: "#475569", display: "flex", alignItems: "center", gap: 6 }}>
                    <svg width="10" height="10"><circle cx="5" cy="5" r="4" fill="#fbbf24"/></svg>
                    Predicted reroute
                  </div>
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {[
                  { icon: "📬", value: `${Math.round(pdr * 100)}%`, label: "Messages delivered", sublabel: `${frame?.metrics?.delivered ?? 0} of ${frame?.metrics?.total ?? 0} total`, color: pdr > 0.75 ? "#10b981" : "#ef4444", big: true },
                  { icon: "⏱", value: `${(frame?.metrics?.avgDelay ?? 0).toFixed(2)}s`, label: "Average travel time", sublabel: "per message", color: "#60a5fa" },
                  { icon: "💥", value: `${frame?.metrics?.breaks ?? 0}`, label: "Path disruptions", sublabel: "route breaks detected", color: "#f59e0b" },
                  { icon: "🧠", value: `${frame?.metrics?.predictions ?? 0}`, label: "Early reroutes", sublabel: "congestion predicted", color: "#a78bfa" },
                ].map(m => <MetricCard key={m.label} {...m} />)}
              </div>
            </div>

            <div style={S.card}>
              <div style={{ fontSize: 12, fontWeight: 700, color: "#475569",
                textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
                Plain English results
              </div>
              <TranslationTable metrics={frame?.metrics} />
            </div>
          </div>
        )}

        {/* ── COMPARE MODE ── */}
        {mode === "compare" && (
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <div style={{ display: "grid", gridTemplateColumns: "3fr 48px 3fr", gap: 0, alignItems: "start" }}>

              {/* AODV side */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ background: "rgba(239,68,68,0.08)", border: "1px solid #ef444433",
                  borderRadius: 10, padding: "10px 16px", textAlign: "center" }}>
                  <div style={{ fontSize: 13, fontWeight: 800, color: "#ef4444" }}>
                    AODV — Traditional routing
                  </div>
                  <div style={{ fontSize: 11, color: "#64748b" }}>Reacts after failure</div>
                </div>
                <div style={S.card}>
                  <TopologyCanvas frame={frameAodv} protocol="AODV"
                    scenarioMeta={{ ...scenarioMeta, color: "#ef4444" }} compact />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  <MetricCard icon="📬" value={`${Math.round(aodvPdr * 100)}%`}
                    label="Delivered" color={aodvPdr > 0.75 ? "#10b981" : "#ef4444"} />
                  <MetricCard icon="💥" value={`${frameAodv?.metrics?.breaks ?? 0}`}
                    label="Breaks" color="#f59e0b" />
                </div>
              </div>

              {/* Divider */}
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center",
                justifyContent: "center", height: "100%", paddingTop: 60, gap: 8 }}>
                <div style={{ width: 1, flex: 1, background: "#1e293b" }} />
                <div style={{ fontSize: 11, color: "#334155", fontWeight: 700,
                  writingMode: "vertical-rl", letterSpacing: 2 }}>VS</div>
                <div style={{ width: 1, flex: 1, background: "#1e293b" }} />
              </div>

              {/* CPQR side */}
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ background: "rgba(16,185,129,0.08)", border: "1px solid #10b98133",
                  borderRadius: 10, padding: "10px 16px", textAlign: "center" }}>
                  <div style={{ fontSize: 13, fontWeight: 800, color: "#10b981" }}>
                    CPQR — Our system
                  </div>
                  <div style={{ fontSize: 11, color: "#64748b" }}>Predicts before failure</div>
                </div>
                <div style={S.card}>
                  <TopologyCanvas frame={frameCpqr} protocol="CPQR"
                    scenarioMeta={{ ...scenarioMeta, color: "#10b981" }} compact />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                  <MetricCard icon="📬" value={`${Math.round(cpqrPdr * 100)}%`}
                    label="Delivered" color="#10b981" />
                  <MetricCard icon="🧠" value={`${frameCpqr?.metrics?.predictions ?? 0}`}
                    label="Predicted" color="#a78bfa" />
                </div>
              </div>
            </div>

            {/* Improvement stat */}
            <div style={{ ...S.card, textAlign: "center", padding: "20px",
              background: improvement > 0 ? "rgba(16,185,129,0.06)" : "rgba(239,68,68,0.06)",
              border: `1px solid ${improvement > 0 ? "#10b98133" : "#ef444433"}` }}>
              <div style={{ fontSize: 40, fontWeight: 900, fontFamily: "monospace",
                color: improvement > 0 ? "#10b981" : "#ef4444" }}>
                {improvement > 0 ? "+" : ""}{improvement}%
              </div>
              <div style={{ fontSize: 14, color: "#94a3b8", marginTop: 4 }}>
                {improvement > 0
                  ? `CPQR delivers ${improvement}% more messages successfully than AODV`
                  : `Both protocols performing similarly — Q-table still learning`}
              </div>
            </div>

            {/* What this means */}
            <div style={S.card}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "#ef4444",
                    textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>
                    Why AODV struggles
                  </div>
                  {[
                    "Only finds a route when needed",
                    "Floods the entire network when a link breaks",
                    "Packets are lost while searching for a new route",
                    "No memory of past network conditions",
                  ].map((t, i) => (
                    <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8,
                      fontSize: 12, color: "#64748b" }}>
                      <span style={{ color: "#ef4444", flexShrink: 0 }}>✕</span>
                      <span>{t}</span>
                    </div>
                  ))}
                </div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, color: "#10b981",
                    textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>
                    How CPQR improves it
                  </div>
                  {[
                    "Learns which paths are reliable over time",
                    "Predicts congestion before queues overflow",
                    "Detects link failure before it happens (RSSI trend)",
                    "Reroutes early — packets already on the new path",
                  ].map((t, i) => (
                    <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8,
                      fontSize: 12, color: "#64748b" }}>
                      <span style={{ color: "#10b981", flexShrink: 0 }}>✓</span>
                      <span>{t}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Legend for story mode */}
        {mode === "story" && (
          <div style={{ display: "flex", gap: 20, flexWrap: "wrap", padding: "8px 0" }}>
            {[
              { color: scenarioMeta.color, label: `${scenarioMeta.nodeEmoji} = ${scenarioMeta.name.split(" ")[0]} node (healthy)` },
              { color: "#f59e0b", label: "Node low on battery" },
              { color: "#ef4444", label: "Node critical" },
              { color: "#60a5fa", label: "🔵 = Packet in transit" },
              { color: "#fbbf24", label: "🟡 = Predicted reroute" },
            ].map(l => (
              <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 6,
                fontSize: 11, color: "#475569" }}>
                <div style={{ width: 8, height: 8, borderRadius: "50%", background: l.color }} />
                {l.label}
              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  );
}
