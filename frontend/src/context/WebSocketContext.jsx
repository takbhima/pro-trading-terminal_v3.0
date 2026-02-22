/**
 * WebSocketContext — Single Responsibility: manage WS lifecycle.
 * All components subscribe via useWebSocket() — no direct WS access elsewhere.
 */
import { createContext, useContext, useEffect, useRef, useState, useCallback } from "react";

const Ctx = createContext(null);

export function WebSocketProvider({ children }) {
  const [status,      setStatus]      = useState({ connected: false, openMarkets: [], label: "Connecting…" });
  const [lastTick,    setLastTick]    = useState(null);   // { symbol, price, change, change_pct, bar, active_trade, live_pnl }
  const [lastSignal,  setLastSignal]  = useState(null);   // signal push from WS
  const [lastExit,    setLastExit]    = useState(null);   // exit event from WS
  const wsRef         = useRef(null);
  const reconnRef     = useRef(null);
  const subscribeRef  = useRef({ symbol: null, interval: "5m" });

  const send = useCallback((payload) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(payload));
    }
  }, []);

  const subscribe = useCallback((symbol, interval) => {
    subscribeRef.current = { symbol, interval };
    send({ type: "subscribe", symbol, interval });
  }, [send]);

  const connect = useCallback(() => {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const ws    = new WebSocket(`${proto}//${location.host}/ws`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus(s => ({ ...s, connected: true, label: "Connected" }));
      clearTimeout(reconnRef.current);
      // Re-subscribe after reconnect
      const { symbol, interval } = subscribeRef.current;
      if (symbol) send({ type: "subscribe", symbol, interval });
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
        }
      } catch {}
    };

    ws.onclose = () => {
      setStatus(s => ({ ...s, connected: false, label: "Reconnecting…" }));
      reconnRef.current = setTimeout(connect, 5000);
    };
    ws.onerror = () => ws.close();
  }, [send]);

  useEffect(() => { connect(); return () => { wsRef.current?.close(); clearTimeout(reconnRef.current); }; }, [connect]);

  return (
    <Ctx.Provider value={{ status, lastTick, lastSignal, lastExit, subscribe, send }}>
      {children}
    </Ctx.Provider>
  );
}

export const useWebSocket = () => useContext(Ctx);
