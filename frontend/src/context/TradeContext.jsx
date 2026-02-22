/**
 * TradeContext — Single Responsibility: active trade state + exit events.
 * Listens to WS signals and provides trade CRUD to components.
 */
import { createContext, useContext, useState, useEffect, useRef } from "react";
import { useWebSocket } from "./WebSocketContext";

const Ctx = createContext(null);

export function TradeProvider({ children }) {
  const { lastTick, lastSignal, lastExit } = useWebSocket();
  const [activeTrade, setActiveTrade]   = useState(null);
  const [lastExitEv,  setLastExitEv]    = useState(null);
  const [livePnl,     setLivePnl]       = useState(null);
  const [livePrice,   setLivePrice]     = useState(null);
  const activeSymRef  = useRef(null);

  // Track active symbol externally
  const setActiveSymbol = (sym) => { activeSymRef.current = sym; };

  // On tick — update live price + pnl
  useEffect(() => {
    if (!lastTick) return;
    if (lastTick.symbol === activeSymRef.current) {
      setLivePrice(lastTick.price);
      if (lastTick.live_pnl != null) setLivePnl(lastTick.live_pnl);
      if (lastTick.active_trade && !activeTrade) setActiveTrade(lastTick.active_trade);
    }
  }, [lastTick]);

  // On exit event
  useEffect(() => {
    if (!lastExit) return;
    if (lastExit.symbol === activeSymRef.current || lastExit.type === "exit") {
      setLastExitEv(lastExit);
      setActiveTrade(null);
      setLivePnl(null);
    }
  }, [lastExit]);

  const openTrade  = (trade) => setActiveTrade(trade);
  const clearTrade = ()      => { setActiveTrade(null); setLivePnl(null); };
  const dismissExit = ()     => setLastExitEv(null);

  const forceClose = async (symbol, price) => {
    const res  = await fetch(`/api/trade/${encodeURIComponent(symbol)}?price=${price || 0}`, { method: "DELETE" });
    const data = await res.json();
    if (data.exit) { setLastExitEv(data.exit); clearTrade(); }
    return data.exit;
  };

  return (
    <Ctx.Provider value={{
      activeTrade, livePrice, livePnl, lastExitEv,
      openTrade, clearTrade, dismissExit, forceClose, setActiveSymbol,
    }}>
      {children}
    </Ctx.Provider>
  );
}

export const useTrade = () => useContext(Ctx);
