// TopologyCanvas.jsx – animated SVG mesh visualisation
export default function TopologyCanvas({ frame, protocol, scenarioColor, compact, showLegend }) {
  const W = 700, H = compact ? 230 : 440;

  const nodeColor = (nd) => {
    if (nd.dead) return "#1e293b";
    if (nd.energy > 0.6) return scenarioColor;
    if (nd.energy > 0.3) return "#f59e0b";
    return "#ef4444";
  };

  const edgeColor = (q) => {
    const r = Math.round(255 * (1 - q));
    const g = Math.round(180 * q);
    return `rgba(${r},${g},80,${0.25 + q * 0.55})`;
  };

  const protoColors = { CPQR: "#10b981", AODV: "#ef4444", OLSR: "#3b82f6", Q_ROUTING: "#a78bfa", PQR: "#f59e0b", DRL: "#06b6d4" };
  const pColor = protoColors[protocol] || scenarioColor;

  if (!frame) return (
    <div style={{ width: "100%", height: H, background: "radial-gradient(ellipse at 30% 30%, #0d0d2b 0%, #05050f 100%)",
      borderRadius: 12, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 12,
      border: "1px solid rgba(255,255,255,0.06)" }}>
      <div style={{ width: 36, height: 36, border: `3px solid ${pColor}33`, borderTopColor: pColor,
        borderRadius: "50%", animation: "spin 1s linear infinite" }} />
      <div style={{ color: "#334155", fontSize: 13, fontWeight: 600 }}>Initialising simulation…</div>
    </div>
  );

  const { nodes, links, packets } = frame;

  return (
    <div style={{ position: "relative", width: "100%" }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: H, display: "block",
        background: "radial-gradient(ellipse at 30% 30%, #0d0d2b 0%, #05050f 100%)",
        borderRadius: 12, border: "1px solid rgba(255,255,255,0.06)" }}
        preserveAspectRatio="xMidYMid meet">

        <defs>
          <pattern id={`grid-${protocol}`} width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(255,255,255,0.025)" strokeWidth="1"/>
          </pattern>
          <filter id="glow">
            <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
            <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <radialGradient id={`node-grad-${protocol}`} cx="35%" cy="35%" r="60%">
            <stop offset="0%" stopColor={pColor} stopOpacity="0.9"/>
            <stop offset="100%" stopColor={pColor} stopOpacity="0.5"/>
          </radialGradient>
        </defs>

        <rect width={W} height={H} fill={`url(#grid-${protocol})`}/>

        {/* Glow radial */}
        <ellipse cx={W * 0.3} cy={H * 0.3} rx={W * 0.4} ry={H * 0.4}
          fill={`${pColor}06`} />

        {/* Edges */}
        {links.map(l => (
          <line key={l.key} x1={l.a.x} y1={l.a.y} x2={l.b.x} y2={l.b.y}
            stroke={edgeColor(l.quality)} strokeWidth={0.8 + l.quality * 1.2}
            strokeLinecap="round" opacity={0.7} />
        ))}

        {/* Packets */}
        {packets.slice(0, 40).map(p => (
          <g key={p.id}>
            <circle cx={p.x} cy={p.y} r={p.predicted ? 5 : 3.5}
              fill={p.predicted ? "#fbbf24" : "#60a5fa"} opacity={0.95}
              filter="url(#glow)">
              <animate attributeName="r" values={p.predicted ? "4;6;4" : "2.5;4.5;2.5"}
                dur="0.8s" repeatCount="indefinite"/>
            </circle>
            {p.predicted && (
              <circle cx={p.x} cy={p.y} r={8} fill="none" stroke="#fbbf24" strokeWidth={1} opacity={0.3}>
                <animate attributeName="r" values="6;14;6" dur="1.1s" repeatCount="indefinite"/>
                <animate attributeName="opacity" values="0.3;0;0.3" dur="1.1s" repeatCount="indefinite"/>
              </circle>
            )}
          </g>
        ))}

        {/* Nodes */}
        {nodes.map(nd => (
          <g key={nd.id}>
            {!nd.dead && (
              <circle cx={nd.x} cy={nd.y} r={18} fill={nodeColor(nd)} opacity={0.08}>
                <animate attributeName="r" values="14;20;14" dur="3s" repeatCount="indefinite"/>
                <animate attributeName="opacity" values="0.08;0.04;0.08" dur="3s" repeatCount="indefinite"/>
              </circle>
            )}
            <circle cx={nd.x} cy={nd.y} r={nd.dead ? 6 : 9}
              fill={nd.dead ? "#0f172a" : `url(#node-grad-${protocol})`}
              stroke={nd.dead ? "#1e293b" : `${nodeColor(nd)}99`}
              strokeWidth={nd.dead ? 1 : 1.5}
              filter={nd.dead ? undefined : "url(#glow)"}/>
            {!nd.dead && nd.queue > 1.5 && (
              <circle cx={nd.x + 9} cy={nd.y - 9} r={4} fill="#ef4444" opacity={0.9}>
                <animate attributeName="r" values="3;5;3" dur="0.5s" repeatCount="indefinite"/>
              </circle>
            )}
          </g>
        ))}

        {/* Protocol badge */}
        <rect x={W - 90} y={H - 28} width={86} height={22} rx={6}
          fill={`${pColor}22`} stroke={pColor} strokeWidth={1}/>
        <text x={W - 47} y={H - 13} textAnchor="middle" fontSize={9}
          fill={pColor} fontFamily="'JetBrains Mono', monospace" fontWeight="700">
          {protocol} ACTIVE
        </text>

        {/* Node count */}
        <text x={12} y={H - 12} fontSize={9} fill="#334155" fontFamily="'JetBrains Mono', monospace">
          {nodes.filter(n => !n.dead).length} nodes · {links.length} links
        </text>
      </svg>

      {showLegend && (
        <div style={{ display: "flex", gap: 16, marginTop: 10, flexWrap: "wrap" }}>
          {[
            { color: scenarioColor, label: "Healthy node" },
            { color: "#f59e0b",     label: "Low battery" },
            { color: "#ef4444",     label: "Critical" },
            { color: "#60a5fa",     label: "Packet in transit" },
            { color: "#fbbf24",     label: "Predicted reroute" },
          ].map(l => (
            <div key={l.label} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "#475569" }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: l.color, flexShrink: 0 }}/>
              {l.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
