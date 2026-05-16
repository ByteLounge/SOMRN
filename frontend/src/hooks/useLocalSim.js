// Local simulation engine — used as fallback when backend is offline
import { useState, useEffect, useRef, useCallback } from "react";

function createNode(id, w, h) {
  return {
    id, x: 60 + Math.random() * (w - 120), y: 60 + Math.random() * (h - 120),
    vx: (Math.random() - 0.5) * 0.6, vy: (Math.random() - 0.5) * 0.6,
    energy: 0.8 + Math.random() * 0.2, queue: 0, dead: false,
  };
}
function dist(a, b) { return Math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2); }

export function useLocalSim(scenario, protocol, running) {
  const RANGE = 160, W = 700, H = 420;
  const stateRef = useRef(null);
  const [frame, setFrame] = useState(null);
  const rafRef = useRef(null);
  const tickRef = useRef(0);
  const metricRef = useRef({ delivered: 0, dropped: 0, total: 0, delay: 0, breaks: 0, predictions: 0 });
  const events = useRef([]);

  const pushEvent = (msg, type) => {
    events.current = [{ msg, type, id: Date.now() + Math.random() }, ...events.current].slice(0, 6);
  };

  const reset = useCallback(() => {
    const cfg = {
      earthquake: { n: 28, speed: 1.1, trafficRate: 0.18 },
      campus:     { n: 20, speed: 0.45, trafficRate: 0.10 },
      drone:      { n: 16, speed: 1.8, trafficRate: 0.22 },
    }[scenario] || { n: 22, speed: 0.7, trafficRate: 0.13 };
    stateRef.current = {
      nodes: Array.from({ length: cfg.n }, (_, i) => createNode(i, W, H)),
      packets: [], cfg, links: [], prevEdges: new Set(),
    };
    metricRef.current = { delivered: 0, dropped: 0, total: 0, delay: 0, breaks: 0, predictions: 0 };
    events.current = [];
    tickRef.current = 0;
    pushEvent(`Simulation started`, "info");
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

      nodes.forEach(nd => {
        if (nd.dead) return;
        nd.x += nd.vx * cfg.speed; nd.y += nd.vy * cfg.speed;
        if (nd.x < 30 || nd.x > W - 30) { nd.vx *= -1; nd.x = Math.max(30, Math.min(W - 30, nd.x)); }
        if (nd.y < 30 || nd.y > H - 30) { nd.vy *= -1; nd.y = Math.max(30, Math.min(H - 30, nd.y)); }
        nd.vx += (Math.random() - 0.5) * 0.04; nd.vy += (Math.random() - 0.5) * 0.04;
        nd.vx = Math.max(-1.5, Math.min(1.5, nd.vx)); nd.vy = Math.max(-1.5, Math.min(1.5, nd.vy));
        nd.queue = Math.max(0, nd.queue - 0.08);
      });

      const alive = nodes.filter(n => !n.dead);
      const newEdges = new Set();
      const links = [];
      for (let i = 0; i < alive.length; i++) {
        for (let j = i + 1; j < alive.length; j++) {
          const d = dist(alive[i], alive[j]);
          if (d < RANGE) {
            const key = `${alive[i].id}-${alive[j].id}`;
            newEdges.add(key);
            links.push({ a: alive[i], b: alive[j], quality: Math.max(0, 1 - d / RANGE), key });
          }
        }
      }
      s.prevEdges.forEach(k => {
        if (!newEdges.has(k)) {
          metricRef.current.breaks++;
          if (t % 15 === 0) pushEvent(`🔴 Link lost — rerouting`, "warning");
        }
      });
      s.prevEdges = newEdges; s.links = links;

      if (Math.random() < cfg.trafficRate && alive.length > 2) {
        const src = alive[Math.floor(Math.random() * alive.length)];
        const dsts = alive.filter(n => n.id !== src.id);
        const dst = dsts[Math.floor(Math.random() * dsts.length)];
        packets.push({
          id: t + Math.random(), srcId: src.id, dstId: dst.id,
          x: src.x, y: src.y, targetX: dst.x, targetY: dst.y,
          progress: 0, life: 0, hops: Math.floor(1 + Math.random() * 3),
          predicted: ["CPQR","PQR","DRL"].includes(protocol) && Math.random() < 0.55,
        });
        metricRef.current.total++;
      }

      const alivePkts = [];
      packets.forEach(p => {
        p.progress += 0.025 + Math.random() * 0.01; p.life++;
        p.x += (p.targetX - p.x) * 0.06; p.y += (p.targetY - p.y) * 0.06;
        const dn = nodes[p.dstId];
        if (dn) { p.targetX = dn.x; p.targetY = dn.y; }
        if (p.progress >= 1 || p.life > 120) {
          const DROP_RATE = {
            CPQR:      0.10, // best — predicts congestion
            DRL:       0.11, // near best — learns deep patterns
            PQR:       0.14, // predictive q-routing
            Q_ROUTING: 0.17, // pure q-routing
            OLSR:      0.20, // proactive but no ML
            AODV:      0.28, // reactive, no memory
          };
          const dropRate = DROP_RATE[protocol] ?? 0.22;
          const success = p.progress >= 1 || Math.random() > dropRate;
          if (success) {
            metricRef.current.delivered++;
            metricRef.current.delay += 0.1 + p.hops * 0.08 + Math.random() * 0.05;
            if (t % 20 === 0) pushEvent(`✅ Delivered in ${p.hops} hops`, "success");
            if (p.predicted && t % 30 === 0) { metricRef.current.predictions++; pushEvent(`🟡 Predicted reroute`, "predict"); }
          } else {
            metricRef.current.dropped++;
            if (t % 25 === 0) pushEvent(`❌ Message lost`, "error");
          }
        } else { alivePkts.push(p); }
      });
      s.packets = alivePkts;

      if (["CPQR","Q_ROUTING","DRL","PQR"].includes(protocol) && t > 80 && Math.random() < 0.002) {
        const labels = { CPQR: "🧠 Q-table updated", Q_ROUTING: "🤖 Q-routing converging", DRL: "🧬 DRL policy updated", PQR: "🔮 PQR rerouting" };
        pushEvent(labels[protocol] || "🧠 Learning update", "learn");
      }
      if (t % 60 === 0) nodes.forEach(nd => { if (!nd.dead) nd.energy = Math.max(0, nd.energy - 0.002 * Math.random()); });

      const m = metricRef.current;
      const pdr = m.total > 0 ? m.delivered / m.total : 0;
      const avgDelay = m.delivered > 0 ? m.delay / m.delivered : 0;
      setFrame({ nodes: nodes.map(n => ({ ...n })), links: [...s.links], packets: [...s.packets],
        metrics: { ...m, pdr, avgDelay }, events: [...events.current], t });
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [running, protocol, scenario]);

  return frame;
}
