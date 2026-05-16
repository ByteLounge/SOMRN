// ResultsChart.jsx – draws line/bar charts from CSV result data using pure SVG
import { useMemo } from "react";

const PAD = { top: 18, right: 20, bottom: 36, left: 52 };

function lerp(a, b, t) { return a + (t - a) / (b - a || 1) * (b - a); }

function buildPath(points, w, h, minY, maxY, minX, maxX) {
  if (!points || points.length < 2) return "";
  const px = (x) => PAD.left + ((x - minX) / (maxX - minX || 1)) * (w - PAD.left - PAD.right);
  const py = (y) => PAD.top + (1 - (y - minY) / (maxY - minY || 1)) * (h - PAD.top - PAD.bottom);
  let d = `M ${px(points[0].x)} ${py(points[0].y)}`;
  for (let i = 1; i < points.length; i++) {
    const cp1x = px(points[i - 1].x) + (px(points[i].x) - px(points[i - 1].x)) * 0.45;
    const cp1y = py(points[i - 1].y);
    const cp2x = px(points[i - 1].x) + (px(points[i].x) - px(points[i - 1].x)) * 0.55;
    const cp2y = py(points[i].y);
    d += ` C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${px(points[i].x)} ${py(points[i].y)}`;
  }
  return d;
}

const PROTO_COLORS = {
  AODV:  { line: "#ef4444", fill: "rgba(239,68,68,0.12)" },
  OLSR:  { line: "#3b82f6", fill: "rgba(59,130,246,0.12)" },
  CPQR:  { line: "#10b981", fill: "rgba(16,185,129,0.15)" },
  Q_ROUTING: { line: "#a78bfa", fill: "rgba(167,139,250,0.12)" },
  PQR:   { line: "#f59e0b", fill: "rgba(245,158,11,0.12)" },
  DRL:   { line: "#06b6d4", fill: "rgba(6,182,212,0.12)" },
};

export default function ResultsChart({ results, metric = "pdr", title = "Packet Delivery Ratio", yLabel = "PDR", yFormat }) {
  const W = 540, H = 260;

  const series = useMemo(() => {
    if (!results) return [];
    return Object.entries(results).map(([proto, rows]) => {
      const pts = rows
        .filter(r => r.time !== undefined && r[metric] !== undefined)
        .map(r => ({ x: r.time, y: r[metric] }));
      return { proto, pts, color: PROTO_COLORS[proto] || { line: "#8b5cf6", fill: "rgba(139,92,246,0.1)" } };
    }).filter(s => s.pts.length > 0);
  }, [results, metric]);

  const allX = series.flatMap(s => s.pts.map(p => p.x));
  const allY = series.flatMap(s => s.pts.map(p => p.y));
  const minX = Math.min(...allX, 0), maxX = Math.max(...allX, 1);
  const rawMin = Math.min(...allY), rawMax = Math.max(...allY);
  const minY = rawMin - (rawMax - rawMin) * 0.05;
  const maxY = rawMax + (rawMax - rawMin) * 0.08;

  const px = (x) => PAD.left + ((x - minX) / (maxX - minX || 1)) * (W - PAD.left - PAD.right);
  const py = (y) => PAD.top + (1 - (y - minY) / (maxY - minY || 1)) * (H - PAD.top - PAD.bottom);

  const yTicks = 5;
  const xTicks = 6;

  const fmt = yFormat || (v => v < 1 && v > -1 ? (v * 100).toFixed(0) + "%" : v.toFixed ? v.toFixed(1) : v);

  if (!results) return (
    <div style={{ height: H, display: "flex", alignItems: "center", justifyContent: "center",
      color: "#334155", fontSize: 13 }}>No results data available</div>
  );

  return (
    <div>
      <div style={{ fontSize: 11, color: "#64748b", fontWeight: 700, textTransform: "uppercase",
        letterSpacing: 1, marginBottom: 10 }}>{title}</div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: H, overflow: "visible" }}>
        <defs>
          {series.map(({ proto, color }) => (
            <linearGradient key={proto} id={`fill-${proto}-${metric}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color.line} stopOpacity="0.25"/>
              <stop offset="100%" stopColor={color.line} stopOpacity="0"/>
            </linearGradient>
          ))}
        </defs>

        {/* Y-axis grid + labels */}
        {Array.from({ length: yTicks }).map((_, i) => {
          const v = minY + (maxY - minY) * (i / (yTicks - 1));
          const y = py(v);
          return (
            <g key={i}>
              <line x1={PAD.left} y1={y} x2={W - PAD.right} y2={y}
                stroke="rgba(255,255,255,0.04)" strokeWidth={1}/>
              <text x={PAD.left - 6} y={y + 4} textAnchor="end" fontSize={9}
                fill="#475569" fontFamily="'JetBrains Mono',monospace">
                {fmt(v)}
              </text>
            </g>
          );
        })}

        {/* X-axis ticks */}
        {Array.from({ length: xTicks }).map((_, i) => {
          const v = minX + (maxX - minX) * (i / (xTicks - 1));
          const x = px(v);
          return (
            <g key={i}>
              <line x1={x} y1={PAD.top} x2={x} y2={H - PAD.bottom}
                stroke="rgba(255,255,255,0.03)" strokeWidth={1}/>
              <text x={x} y={H - PAD.bottom + 14} textAnchor="middle" fontSize={9}
                fill="#334155" fontFamily="'JetBrains Mono',monospace">
                {v.toFixed(0)}s
              </text>
            </g>
          );
        })}

        {/* Axis lines */}
        <line x1={PAD.left} y1={PAD.top} x2={PAD.left} y2={H - PAD.bottom}
          stroke="rgba(255,255,255,0.08)" strokeWidth={1}/>
        <line x1={PAD.left} y1={H - PAD.bottom} x2={W - PAD.right} y2={H - PAD.bottom}
          stroke="rgba(255,255,255,0.08)" strokeWidth={1}/>

        {/* Area fills */}
        {series.map(({ proto, pts, color }) => {
          if (pts.length < 2) return null;
          const linePath = buildPath(pts, W, H, minY, maxY, minX, maxX);
          const areaPath = linePath + ` L ${px(pts[pts.length - 1].x)} ${H - PAD.bottom} L ${px(pts[0].x)} ${H - PAD.bottom} Z`;
          return (
            <path key={`area-${proto}`} d={areaPath}
              fill={`url(#fill-${proto}-${metric})`} strokeWidth={0}/>
          );
        })}

        {/* Lines */}
        {series.map(({ proto, pts, color }) => {
          if (pts.length < 2) return null;
          const linePath = buildPath(pts, W, H, minY, maxY, minX, maxX);
          return (
            <path key={`line-${proto}`} d={linePath} fill="none"
              stroke={color.line} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"/>
          );
        })}

        {/* Dots at last point */}
        {series.map(({ proto, pts, color }) => {
          const last = pts[pts.length - 1];
          if (!last) return null;
          return (
            <circle key={`dot-${proto}`} cx={px(last.x)} cy={py(last.y)} r={4}
              fill={color.line} stroke="#05050f" strokeWidth={2}/>
          );
        })}
      </svg>

      {/* Legend */}
      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginTop: 6 }}>
        {series.map(({ proto, color }) => (
          <div key={proto} style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11 }}>
            <div style={{ width: 20, height: 2, background: color.line, borderRadius: 1 }}/>
            <span style={{ color: "#64748b", fontFamily: "'JetBrains Mono',monospace", fontWeight: 600 }}>{proto}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
