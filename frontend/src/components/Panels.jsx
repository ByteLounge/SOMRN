import { useState } from "react";
import TopologyCanvas from "./TopologyCanvas.jsx";
import { MetricCard, StatBar, EventFeed } from "./UIComponents.jsx";
import ResultsChart from "./ResultsChart.jsx";

const SCENARIOS = {
  earthquake: { name: "Earthquake Response", emoji: "🆘", color: "#ef4444", tagline: "Emergency responders in crisis zones", backendKey: "earthquake" },
  campus:     { name: "Campus Mesh",         emoji: "🎓", color: "#3b82f6", tagline: "Students moving between buildings",     backendKey: "campus" },
  drone:      { name: "Drone Swarm",         emoji: "🚁", color: "#10b981", tagline: "Drones coordinating a search mission",  backendKey: "drone" },
};

const PROTOCOLS = ["AODV", "OLSR", "CPQR"];

// ── Intro screen ─────────────────────────────────────────────────────────────
export function IntroScreen({ scenario, setScenario, onStart }) {
  const meta = SCENARIOS[scenario];
  return (
    <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center", padding: "40px 24px" }}>
      <div style={{ maxWidth: 660, width: "100%", textAlign: "center", display: "flex", flexDirection: "column", gap: 28, alignItems: "center" }}>
        <div style={{ position: "relative" }}>
          <div style={{ fontSize: 72, filter: "drop-shadow(0 0 30px rgba(139,92,246,0.5))" }}>📡</div>
          <div style={{ position: "absolute", inset: -20, borderRadius: "50%",
            background: "radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%)",
            animation: "pulse-ring 2s ease-in-out infinite" }}/>
        </div>

        <div>
          <div style={{ fontSize: 32, fontWeight: 900, marginBottom: 12, lineHeight: 1.2,
            background: "linear-gradient(135deg, #e2e8f0, #8b5cf6, #06b6d4)",
            WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Self-Optimizing Mesh Routing
          </div>
          <div style={{ fontSize: 15, color: "#64748b", lineHeight: 1.75, maxWidth: 520, margin: "0 auto" }}>
            CPQR uses Q-learning to predict congestion and route failures <em>before</em> they happen.
            Compare it live against AODV and OLSR.
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, width: "100%", textAlign: "left" }}>
          {[
            { icon: "🔴", title: "Traditional (AODV)", body: "Floods the network on failure. Messages lost while route is rediscovered. No memory of past conditions." },
            { icon: "🟢", title: "CPQR — Our System",  body: "Learns reliable paths via Q-tables. Predicts failures from RSSI trends. Reroutes early — zero packet loss." },
          ].map(c => (
            <div key={c.title} style={{ background: "rgba(255,255,255,0.04)", borderRadius: 14,
              border: "1px solid rgba(255,255,255,0.07)", padding: 18,
              transition: "all 0.2s" }}>
              <div style={{ fontSize: 28, marginBottom: 10 }}>{c.icon}</div>
              <div style={{ fontWeight: 700, marginBottom: 6, fontSize: 13, color: "#e2e8f0" }}>{c.title}</div>
              <div style={{ fontSize: 12, color: "#64748b", lineHeight: 1.6 }}>{c.body}</div>
            </div>
          ))}
        </div>

        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", justifyContent: "center" }}>
          {Object.entries(SCENARIOS).map(([k, v]) => (
            <button key={k} onClick={() => setScenario(k)} style={{
              padding: "7px 16px", borderRadius: 20,
              border: `1px solid ${scenario === k ? v.color : "rgba(255,255,255,0.08)"}`,
              background: scenario === k ? `${v.color}20` : "transparent",
              color: scenario === k ? v.color : "#64748b",
              fontSize: 13, fontWeight: 600, cursor: "pointer", transition: "all 0.2s",
            }}>
              {v.emoji} {v.name}
            </button>
          ))}
        </div>

        <button onClick={onStart} style={{
          padding: "15px 44px", borderRadius: 14, border: "none",
          background: `linear-gradient(135deg, ${meta.color}, ${meta.color}cc)`,
          color: meta.color === "#3b82f6" ? "#fff" : "#000",
          fontSize: 15, fontWeight: 800, cursor: "pointer",
          boxShadow: `0 8px 32px ${meta.color}44`, transition: "all 0.2s",
        }}>
          {meta.emoji} Launch {meta.name} →
        </button>
      </div>
    </div>
  );
}

// ── Story mode ────────────────────────────────────────────────────────────────
export function StoryMode({ frame, scenario, protocol, backendEvents }) {
  const meta = SCENARIOS[scenario];
  const pdr   = frame?.metrics?.pdr ?? 0;
  const evts  = backendEvents?.length ? backendEvents : (frame?.events ?? []);
  const CARD  = { background: "rgba(255,255,255,0.035)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 14, padding: 20 };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14 }}>
        <div style={CARD}>
          <TopologyCanvas frame={frame} protocol={protocol} scenarioColor={meta.color} compact={false} showLegend />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={CARD}><EventFeed events={evts} /></div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <MetricCard icon="📬" value={`${Math.round(pdr * 100)}%`} label="Delivered"
              sublabel="of all messages" color={pdr > 0.7 ? "#10b981" : "#ef4444"} />
            <MetricCard icon="⚡" value={frame?.metrics?.breaks ?? 0} label="Disruptions"
              sublabel="path breaks" color="#f59e0b" />
            <MetricCard icon="🔵" value={frame?.packets?.length ?? 0} label="In Flight"
              sublabel="right now" color="#60a5fa" />
            <MetricCard icon="🧠" value={frame?.metrics?.predictions ?? 0} label="Predicted"
              sublabel="reroutes" color="#a78bfa" />
          </div>
        </div>
      </div>
      <div style={CARD}>
        <div style={{ fontSize: 11, color: "#475569", fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
          What the numbers mean
        </div>
        <TranslationTable metrics={frame?.metrics} />
      </div>
    </div>
  );
}

// ── Single protocol mode ───────────────────────────────────────────────────────
export function SingleMode({ frame, scenario, protocol, backendEvents }) {
  const meta = SCENARIOS[scenario];
  const pdr = frame?.metrics?.pdr ?? 0;
  const CARD = { background: "rgba(255,255,255,0.035)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 14, padding: 20 };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 14 }}>
        <div style={CARD}>
          <TopologyCanvas frame={frame} protocol={protocol} scenarioColor={meta.color} compact={false} showLegend />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {[
            { icon: "📬", value: `${Math.round(pdr * 100)}%`, label: "Delivered", sublabel: `${frame?.metrics?.delivered ?? 0} of ${frame?.metrics?.total ?? 0}`, color: pdr > 0.75 ? "#10b981" : "#ef4444", big: true },
            { icon: "⏱",  value: `${(frame?.metrics?.avgDelay ?? 0).toFixed(2)}s`, label: "Avg Delay", sublabel: "per message", color: "#60a5fa" },
            { icon: "💥", value: frame?.metrics?.breaks ?? 0, label: "Path Breaks", sublabel: "route disruptions", color: "#f59e0b" },
            { icon: "🧠", value: frame?.metrics?.predictions ?? 0, label: "Early Reroutes", sublabel: "predicted by CPQR", color: "#a78bfa" },
          ].map(m => <MetricCard key={m.label} {...m} />)}
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        <div style={CARD}>
          <EventFeed events={backendEvents?.length ? backendEvents : (frame?.events ?? [])} />
        </div>
        <div style={CARD}>
          <div style={{ fontSize: 11, color: "#475569", fontWeight: 700, textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>Plain English</div>
          <TranslationTable metrics={frame?.metrics} />
        </div>
      </div>
    </div>
  );
}

// ── Compare mode ──────────────────────────────────────────────────────────────
export function CompareMode({ frameAodv, frameCpqr, scenario }) {
  const meta = SCENARIOS[scenario];
  const aodvPdr = frameAodv?.metrics?.pdr ?? 0;
  const cpqrPdr = frameCpqr?.metrics?.pdr ?? 0;
  const improvement = Math.round((cpqrPdr - aodvPdr) * 100);
  const CARD = { background: "rgba(255,255,255,0.035)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 14, padding: 16 };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 44px 1fr", gap: 0, alignItems: "start" }}>
        {/* AODV */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ background: "rgba(239,68,68,0.07)", border: "1px solid rgba(239,68,68,0.2)",
            borderRadius: 10, padding: "10px 16px", textAlign: "center" }}>
            <div style={{ fontWeight: 800, color: "#ef4444", fontSize: 13 }}>AODV — Traditional</div>
            <div style={{ fontSize: 11, color: "#64748b" }}>Reacts after failure</div>
          </div>
          <div style={CARD}>
            <TopologyCanvas frame={frameAodv} protocol="AODV" scenarioColor="#ef4444" compact />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <MetricCard icon="📬" value={`${Math.round(aodvPdr * 100)}%`} label="Delivered" color={aodvPdr > 0.75 ? "#10b981" : "#ef4444"} />
            <MetricCard icon="💥" value={frameAodv?.metrics?.breaks ?? 0} label="Breaks" color="#f59e0b" />
          </div>
        </div>

        {/* VS divider */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: 340, paddingTop: 48, gap: 8 }}>
          <div style={{ width: 1, flex: 1, background: "rgba(255,255,255,0.06)" }}/>
          <div style={{ fontSize: 9, color: "#334155", fontWeight: 800, writingMode: "vertical-rl", letterSpacing: 2 }}>VS</div>
          <div style={{ width: 1, flex: 1, background: "rgba(255,255,255,0.06)" }}/>
        </div>

        {/* CPQR */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ background: "rgba(16,185,129,0.07)", border: "1px solid rgba(16,185,129,0.2)",
            borderRadius: 10, padding: "10px 16px", textAlign: "center" }}>
            <div style={{ fontWeight: 800, color: "#10b981", fontSize: 13 }}>CPQR — Our System</div>
            <div style={{ fontSize: 11, color: "#64748b" }}>Predicts before failure</div>
          </div>
          <div style={CARD}>
            <TopologyCanvas frame={frameCpqr} protocol="CPQR" scenarioColor="#10b981" compact />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <MetricCard icon="📬" value={`${Math.round(cpqrPdr * 100)}%`} label="Delivered" color="#10b981" />
            <MetricCard icon="🧠" value={frameCpqr?.metrics?.predictions ?? 0} label="Predicted" color="#a78bfa" />
          </div>
        </div>
      </div>

      {/* Improvement badge */}
      <div style={{ ...CARD, textAlign: "center", padding: "22px",
        background: improvement > 0 ? "rgba(16,185,129,0.06)" : "rgba(239,68,68,0.06)",
        border: `1px solid ${improvement > 0 ? "rgba(16,185,129,0.2)" : "rgba(239,68,68,0.2)"}` }}>
        <div style={{ fontSize: 44, fontWeight: 900, fontFamily: "'JetBrains Mono',monospace",
          color: improvement > 0 ? "#10b981" : "#ef4444" }}>
          {improvement > 0 ? "+" : ""}{improvement}%
        </div>
        <div style={{ fontSize: 14, color: "#94a3b8", marginTop: 6 }}>
          {improvement > 0 ? `CPQR delivers ${improvement}% more messages than AODV` : "Q-table still learning — keep watching"}
        </div>
      </div>

      {/* Why */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        {[
          { color: "#ef4444", title: "Why AODV struggles", items: ["Floods network on link failure", "Packets lost during route search", "No memory of past conditions", "High control overhead"] },
          { color: "#10b981", title: "How CPQR improves it", items: ["Learns reliable paths via Q-tables", "Predicts congestion before it peaks", "Detects failure via RSSI trends", "Reroutes early — no packet loss"] },
        ].map(col => (
          <div key={col.title} style={CARD}>
            <div style={{ fontSize: 11, fontWeight: 700, color: col.color, textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>{col.title}</div>
            {col.items.map((t, i) => (
              <div key={i} style={{ display: "flex", gap: 8, marginBottom: 8, fontSize: 12, color: "#64748b" }}>
                <span style={{ color: col.color, flexShrink: 0 }}>{col.color === "#ef4444" ? "✕" : "✓"}</span>
                <span>{t}</span>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Results analytics panel ───────────────────────────────────────────────────
export function ResultsPanel({ results }) {
  const [metric, setMetric] = useState("pdr");
  const METRICS = [
    { key: "pdr",           label: "Delivery Rate",  yLabel: "PDR" },
    { key: "avg_delay",     label: "Avg Delay (s)",  yLabel: "Delay" },
    { key: "throughput_bps",label: "Throughput",     yLabel: "bps", yFormat: v => `${(v/1000).toFixed(0)}k` },
    { key: "route_breaks",  label: "Route Breaks",   yLabel: "breaks", yFormat: v => v.toFixed(0) },
  ];
  const CARD = { background: "rgba(255,255,255,0.035)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 14, padding: 20 };

  // Summary stats from last row of each protocol
  const summaryStats = results ? Object.entries(results).map(([proto, rows]) => {
    const last = rows[rows.length - 1] || {};
    return { proto, pdr: last.pdr || 0, delay: last.avg_delay || 0, breaks: last.route_breaks || 0, throughput: last.throughput_bps || 0 };
  }) : [];

  const PROTO_COLORS = { AODV: "#ef4444", OLSR: "#3b82f6", CPQR: "#10b981", Q_ROUTING: "#a78bfa", PQR: "#f59e0b", DRL: "#06b6d4" };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {/* Summary cards */}
      {summaryStats.length > 0 && (
        <div style={{ display: "grid", gridTemplateColumns: `repeat(${summaryStats.length}, 1fr)`, gap: 10 }}>
          {summaryStats.map(s => (
            <div key={s.proto} style={{ ...CARD, borderColor: `${PROTO_COLORS[s.proto] || "#8b5cf6"}30` }}>
              <div style={{ fontSize: 11, fontWeight: 800, color: PROTO_COLORS[s.proto] || "#8b5cf6",
                fontFamily: "'JetBrains Mono',monospace", marginBottom: 12, letterSpacing: 0.5 }}>{s.proto}</div>
              <StatBar label="PDR" value={s.pdr} max={1} color={PROTO_COLORS[s.proto] || "#8b5cf6"} format={v => `${(v*100).toFixed(0)}%`} />
              <div style={{ marginTop: 8 }}>
                <StatBar label="Delay" value={s.delay} max={3} color="#f59e0b" format={v => `${v.toFixed(2)}s`} />
              </div>
              <div style={{ marginTop: 8 }}>
                <StatBar label="Breaks" value={s.breaks} max={Math.max(...summaryStats.map(x => x.breaks), 1)} color="#ef4444" format={v => v.toFixed(0)} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Chart panel */}
      <div style={CARD}>
        <div style={{ display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" }}>
          {METRICS.map(m => (
            <button key={m.key} onClick={() => setMetric(m.key)} style={{
              padding: "5px 14px", borderRadius: 20, fontSize: 11, fontWeight: 700,
              background: metric === m.key ? "rgba(139,92,246,0.2)" : "rgba(255,255,255,0.04)",
              border: `1px solid ${metric === m.key ? "#8b5cf6" : "rgba(255,255,255,0.07)"}`,
              color: metric === m.key ? "#a78bfa" : "#475569", cursor: "pointer", transition: "all 0.2s",
            }}>{m.label}</button>
          ))}
        </div>
        <ResultsChart results={results} metric={metric}
          title={METRICS.find(m => m.key === metric)?.label}
          yFormat={METRICS.find(m => m.key === metric)?.yFormat} />
      </div>

      {!results && (
        <div style={{ ...CARD, textAlign: "center", padding: 40, color: "#334155" }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>📊</div>
          <div style={{ fontWeight: 600, fontSize: 14 }}>No results data available</div>
          <div style={{ fontSize: 12, marginTop: 6, color: "#1e293b" }}>
            Run a simulation with the backend to generate CSV results
          </div>
        </div>
      )}
    </div>
  );
}

// ── Translation table ─────────────────────────────────────────────────────────
export function TranslationTable({ metrics }) {
  const pdr = metrics?.pdr ?? 0;
  const delay = metrics?.avgDelay ?? 0;
  const breaks = metrics?.breaks ?? 0;
  const rows = [
    { label: "Messages delivered", value: `${Math.round(pdr * 100)}%`, plain: `${Math.round(pdr * 100)} of every 100 arrive`, good: pdr > 0.75 },
    { label: "Travel time",        value: `${delay.toFixed(2)}s`,       plain: `Each hop takes ${delay.toFixed(2)}s on average`, good: delay < 0.5 },
    { label: "Path disruptions",   value: `${breaks}`,                  plain: `Route broke ${breaks} times`, good: breaks < 10 },
    { label: "Total sent",         value: metrics?.total ?? 0,          plain: "Messages sent since start", good: true },
  ];
  return (
    <div style={{ background: "rgba(255,255,255,0.02)", borderRadius: 10, border: "1px solid rgba(255,255,255,0.06)", overflow: "hidden" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 70px 1fr", gap: 8, padding: "8px 14px",
        background: "rgba(255,255,255,0.04)", fontSize: 10, fontWeight: 700, color: "#475569",
        textTransform: "uppercase", letterSpacing: 1 }}>
        <span>Metric</span><span>Value</span><span>Plain English</span>
      </div>
      {rows.map((r, i) => (
        <div key={i} style={{ display: "grid", gridTemplateColumns: "1fr 70px 1fr", gap: 8,
          padding: "9px 14px", borderTop: "1px solid rgba(255,255,255,0.04)",
          background: i % 2 ? "rgba(255,255,255,0.01)" : "transparent", alignItems: "center" }}>
          <div style={{ fontSize: 12, color: "#94a3b8", fontWeight: 600 }}>{r.label}</div>
          <div style={{ fontSize: 13, fontWeight: 800, fontFamily: "'JetBrains Mono',monospace",
            color: r.good ? "#10b981" : "#ef4444" }}>{r.value}</div>
          <div style={{ fontSize: 11, color: "#475569" }}>{r.plain}</div>
        </div>
      ))}
    </div>
  );
}
