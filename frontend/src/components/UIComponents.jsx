// MetricCard.jsx
export function MetricCard({ icon, value, label, sublabel, color, trend, big }) {
  return (
    <div style={{
      background: "rgba(255,255,255,0.035)", borderRadius: 14,
      border: `1px solid ${color}28`, padding: big ? "20px 22px" : "14px 16px",
      display: "flex", flexDirection: "column", gap: 5, minWidth: 0,
      position: "relative", overflow: "hidden", transition: "all 0.2s",
    }}
    onMouseEnter={e => { e.currentTarget.style.background = "rgba(255,255,255,0.055)"; e.currentTarget.style.borderColor = `${color}55`; }}
    onMouseLeave={e => { e.currentTarget.style.background = "rgba(255,255,255,0.035)"; e.currentTarget.style.borderColor = `${color}28`; }}>
      {/* Background glow */}
      <div style={{ position: "absolute", bottom: -30, right: -20, width: 80, height: 80,
        borderRadius: "50%", background: color, opacity: 0.06, filter: "blur(20px)", pointerEvents: "none" }}/>
      <div style={{ fontSize: big ? 26 : 20 }}>{icon}</div>
      <div style={{ fontSize: big ? 30 : 22, fontWeight: 800, color,
        fontFamily: "'JetBrains Mono', monospace", lineHeight: 1.1, letterSpacing: -0.5 }}>
        {value}
      </div>
      <div style={{ fontSize: 10, color: "#64748b", fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.8 }}>
        {label}
      </div>
      {sublabel && <div style={{ fontSize: 11, color: "#475569", lineHeight: 1.3 }}>{sublabel}</div>}
      {trend !== undefined && (
        <div style={{ fontSize: 10, color: trend > 0 ? "#10b981" : trend < 0 ? "#ef4444" : "#64748b",
          fontWeight: 700, marginTop: 2 }}>
          {trend > 0 ? "▲" : trend < 0 ? "▼" : "─"} {Math.abs(trend).toFixed(1)}%
        </div>
      )}
    </div>
  );
}

// StatBar.jsx – horizontal metric bar
export function StatBar({ label, value, max, color, format }) {
  const pct = Math.min(100, (value / (max || 1)) * 100);
  const display = format ? format(value) : value.toFixed ? value.toFixed(2) : value;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={{ fontSize: 11, color: "#94a3b8", fontWeight: 600 }}>{label}</span>
        <span style={{ fontSize: 12, color, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace" }}>{display}</span>
      </div>
      <div style={{ height: 5, borderRadius: 3, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
        <div style={{ width: `${pct}%`, height: "100%", borderRadius: 3,
          background: `linear-gradient(90deg, ${color}99, ${color})`,
          transition: "width 0.5s cubic-bezier(0.4,0,0.2,1)" }}/>
      </div>
    </div>
  );
}

// EventFeed.jsx
export function EventFeed({ events }) {
  const colors = {
    success: { bg: "rgba(16,185,129,0.08)", border: "#10b981", text: "#6ee7b7" },
    warning: { bg: "rgba(245,158,11,0.08)", border: "#f59e0b", text: "#fcd34d" },
    error:   { bg: "rgba(239,68,68,0.08)",  border: "#ef4444", text: "#fca5a5" },
    info:    { bg: "rgba(96,165,250,0.08)", border: "#60a5fa", text: "#93c5fd" },
    predict: { bg: "rgba(251,191,36,0.08)", border: "#fbbf24", text: "#fde68a" },
    learn:   { bg: "rgba(167,139,250,0.08)", border: "#a78bfa", text: "#c4b5fd" },
    critical:{ bg: "rgba(239,68,68,0.15)",  border: "#ef4444", text: "#fca5a5" },
  };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ fontSize: 10, color: "#475569", fontWeight: 700, textTransform: "uppercase",
        letterSpacing: 1.2, marginBottom: 4, display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#10b981",
          animation: "liveDot 1.2s ease-in-out infinite" }}/>
        Live Events
      </div>
      {events.length === 0 && (
        <div style={{ color: "#334155", fontSize: 12, padding: "10px 0", fontStyle: "italic" }}>
          Waiting for activity…
        </div>
      )}
      {events.map((e, i) => {
        const c = colors[e.type || e.severity] || colors.info;
        const msg = e.msg || e.message || "";
        return (
          <div key={e.id || i} style={{ background: c.bg, border: `1px solid ${c.border}33`,
            borderLeft: `3px solid ${c.border}`, borderRadius: 8, padding: "8px 12px",
            fontSize: 12, color: c.text, lineHeight: 1.4, opacity: 1 - i * 0.12,
            animation: "slideIn 0.3s ease both" }}>
            {msg}
          </div>
        );
      })}
    </div>
  );
}
