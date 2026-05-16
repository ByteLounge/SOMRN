// Loads pre-computed CSV files from the /results/ folder (served as static assets or via API)
// Falls back to fetching from the backend API
import { useState, useEffect, useRef, useCallback } from "react";

const API = "";

export function useBackendSim() {
  const [status, setStatus]     = useState({ running: false, connected: false, params: {} });
  const [liveState, setLiveState] = useState(null);
  const [results, setResults]   = useState(null);
  const [error, setError]       = useState(null);
  const pollRef = useRef(null);

  // ── Parse CSV text → array of objects ──
  function parseCSV(text) {
    const lines = text.trim().split(/\r?\n/);
    if (lines.length < 2) return [];
    const headers = lines[0].split(",").map(h => h.trim());
    return lines.slice(1).map(line => {
      const vals = line.split(",");
      const obj = {};
      headers.forEach((h, i) => {
        const v = (vals[i] || "").trim();
        obj[h] = isNaN(v) || v === "" ? v : parseFloat(v);
      });
      return obj;
    });
  }

  // ── Check backend, then load results ──
  useEffect(() => {
    // Check backend connectivity
    fetch(`${API}/api/status`, { signal: AbortSignal.timeout(2000) })
      .then(r => r.json())
      .then(d => setStatus(s => ({ ...s, connected: true, running: d.running, params: d.params || {} })))
      .catch(() => setStatus(s => ({ ...s, connected: false })));

    // Try backend /api/results first
    fetch(`${API}/api/results`, { signal: AbortSignal.timeout(3000) })
      .then(r => r.json())
      .then(d => { if (d && !d.error) setResults(d); else tryStaticCSVs(); })
      .catch(() => tryStaticCSVs());
  }, []);

  // ── Load CSVs from /results/ static path ──
  async function tryStaticCSVs() {
    const files = [
      { proto: "AODV", path: "/results/aodv_5.0_42.csv" },
      { proto: "OLSR", path: "/results/olsr_5.0_42.csv" },
      { proto: "CPQR", path: "/results/cpqr_5.0_42.csv" },
    ];
    const data = {};
    await Promise.all(files.map(async ({ proto, path }) => {
      try {
        const r = await fetch(path, { signal: AbortSignal.timeout(2000) });
        if (r.ok) {
          const text = await r.text();
          const rows = parseCSV(text);
          if (rows.length > 0) data[proto] = rows;
        }
      } catch (_) {}
    }));
    if (Object.keys(data).length > 0) setResults(data);
  }

  // ── Poll backend every 400ms when connected ──
  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch(`${API}/api/status`, { signal: AbortSignal.timeout(1500) });
        const d = await r.json();
        setStatus(s => ({ ...s, connected: true, running: d.running, params: d.params || {} }));
        if (d.running) {
          const sr = await fetch(`${API}/api/state`, { signal: AbortSignal.timeout(1500) });
          if (sr.ok) { setLiveState(await sr.json()); setError(null); }
        }
      } catch (_) {
        setStatus(s => ({ ...s, connected: false }));
      }
    };
    pollRef.current = setInterval(poll, 500);
    return () => clearInterval(pollRef.current);
  }, []);

  const startSim = useCallback(async (params) => {
    try {
      const r = await fetch(`${API}/api/start`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      });
      if (r.ok) setStatus(s => ({ ...s, running: true, params }));
    } catch (e) { setError("Failed to start simulation"); }
  }, []);

  const stopSim = useCallback(async () => {
    try {
      await fetch(`${API}/api/stop`, { method: "POST" });
      setStatus(s => ({ ...s, running: false }));
      setLiveState(null);
    } catch (e) { setError("Failed to stop simulation"); }
  }, []);

  const triggerChaos = useCallback(async () => {
    try { await fetch(`${API}/api/chaos`, { method: "POST" }); }
    catch (_) {}
  }, []);

  const refreshResults = useCallback(() => {
    fetch(`${API}/api/results`, { signal: AbortSignal.timeout(3000) })
      .then(r => r.json())
      .then(d => { if (d && !d.error) setResults(d); else tryStaticCSVs(); })
      .catch(() => tryStaticCSVs());
  }, []);

  return { status, liveState, results, error, startSim, stopSim, triggerChaos, refreshResults };
}
