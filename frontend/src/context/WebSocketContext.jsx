/**
 * WebSocketContext — FIX: subscribe now sends strategy so the backend
 * scans the watchlist using the correct strategy per client.
 * Also dispatches "signal_clear" messages from the backend.
 */
import { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";

const Ctx = createContext(null);

export function WebSocketProvider({ children }) {
  const [status,       setStatus]       = useState({ connected: false, openMarkets: [], label: "Connecting…" });
  const [lastTick,     setLastTick]     = useState(null);
  const [lastSignal,   setLastSignal]   = useState(null);
  const [lastExit,     setLastExit]     = useState(null);
  // FIX: new state for signal_clear events so Watchlist can react
  const [lastClear,    setLastClear]    = useState(null);
  const wsRef        = useRef(null);
  const reconnRef    = useRef(null);
  // FIX: store full subscription so reconnect re-sends strategy too
  const subscribeRef = useRef({ symbol: null, interval: "5m", strategy: "pro_mtf" });

  const send = useCallback((payload) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }
  }, []);

  // FIX: accept strategy param and include it in subscribe message
  const subscribe = useCallback((symbol, interval, strategy = "pro_mtf") => {
    subscribeRef.current = { symbol, interval, strategy };
    send({ type: "subscribe", symbol, interval, strategy });
  }, [send]);

  const connect = useCallback(() => {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const ws    = new WebSocket(`${proto}//${location.host}/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus(s => ({ ...s, connected: true, label: "Connected" }));
      clearTimeout(reconnRef.current);
      // Re-subscribe after reconnect — includes strategy
      const { symbol, interval, strategy } = subscribeRef.current;
      if (symbol) send({ type: "subscribe", symbol, interval, strategy });
    };

    ws.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data);
        if (d.type === "status") {
          const open = d.open_markets || [];
          setStatus({
            connected:   true,
            openMarkets: open,
            label:       open.length ? `Open: ${open.join(", ")}` : "Markets closed · Crypto 24/7",
          });
        } else if (d.type === "tick") {
          setLastTick(d);
        } else if (d.type === "signal") {
          setLastSignal({ ...d, _ts: Date.now() });
        } else if (d.type === "exit") {
          setLastExit({ ...d, _ts: Date.now() });
        } else if (d.type === "signal_clear") {
          // FIX: backend says no signal for this symbol on current strategy
          setLastClear({ ...d, _ts: Date.now() });
        }
      } catch {}
    };

    ws.onclose = () => {
      setStatus(s => ({ ...s, connected: false, label: "Reconnecting…" }));
      reconnRef.current = setTimeout(connect, 5000);
    };
    ws.onerror = () => ws.close();
  }, [send]);

  useEffect(() => {
    connect();
    return () => { wsRef.current?.close(); clearTimeout(reconnRef.current); };
  }, [connect]);

  return (
    <Ctx.Provider value={{ status, lastTick, lastSignal, lastExit, lastClear, subscribe, send }}>
      {children}
    </Ctx.Provider>
  );
}

export const useWebSocket = () => useContext(Ctx);
