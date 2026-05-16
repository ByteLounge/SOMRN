import { useState, useEffect, useRef, useCallback } from "react";

const API = "";

export function useBackendSim() {
  const [status, setStatus] = useState({ running: false, connected: false, params: {} });
  const [liveState, setLiveState] = useState(null);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  // ── Check backend connectivity on mount ──
  useEffect(() => {
    fetch(`${API}/api/status`)
      .then(r => r.json())
      .then(d => setStatus(s => ({ ...s, connected: true, running: d.running, params: d.params || {} })))
      .catch(() => setStatus(s => ({ ...s, connected: false })));

    // Fetch pre-computed results
    fetch(`${API}/api/results`)
      .then(r => r.json())
      .then(d => setResults(d))
      .catch(() => setResults(null));
  }, []);

  // ── Poll live state every 400ms when simulation running ──
  useEffect(() => {
    if (!status.connected) return;

    const poll = async () => {
      try {
        const r = await fetch(`${API}/api/status`);
        const d = await r.json();
        setStatus(s => ({ ...s, running: d.running, params: d.params || {} }));

        if (d.running) {
          const sr = await fetch(`${API}/api/state`);
          if (sr.ok) {
            const snap = await sr.json();
            setLiveState(snap);
            setError(null);
          }
        }
      } catch (e) {
        setError("Lost connection to backend");
      }
    };

    pollRef.current = setInterval(poll, 400);
    return () => clearInterval(pollRef.current);
  }, [status.connected]);

  const startSim = useCallback(async (params) => {
    try {
      const r = await fetch(`${API}/api/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(params),
      });
      if (r.ok) setStatus(s => ({ ...s, running: true, params }));
    } catch (e) {
      setError("Failed to start simulation");
    }
  }, []);

  const stopSim = useCallback(async () => {
    try {
      await fetch(`${API}/api/stop`, { method: "POST" });
      setStatus(s => ({ ...s, running: false }));
      setLiveState(null);
    } catch (e) {
      setError("Failed to stop simulation");
    }
  }, []);

  const triggerChaos = useCallback(async () => {
    try {
      await fetch(`${API}/api/chaos`, { method: "POST" });
    } catch (e) {
      setError("Failed to trigger chaos");
    }
  }, []);

  const refreshResults = useCallback(() => {
    fetch(`${API}/api/results`)
      .then(r => r.json())
      .then(d => setResults(d))
      .catch(() => {});
  }, []);

  return { status, liveState, results, error, startSim, stopSim, triggerChaos, refreshResults };
}
