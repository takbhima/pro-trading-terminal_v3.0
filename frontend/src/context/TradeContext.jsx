/**
 * TradeContext — Single Responsibility: active trade state + exit events.
 * Listens to WS signals and provides trade CRUD to components.
 *
 * BUG FIX (v1): activeSymRef.current was never set from outside. This meant
 * `lastTick.symbol === activeSymRef.current` was always `null === "XYZ"` → false,
 * so live PnL and livePrice never updated.
 * FIX: Use activeTrade.symbol directly for the symbol match check.
 *
 * BUG FIX (v2): Removed duplicate setActiveTrade call (was called twice with
 * identical condition in the same effect).
 *
 * BUG FIX (v3): Fixed stale closure in exit useEffect — activeTrade was read
 * inside an effect that only had [lastExit] as dependency, risking stale value.
 * Fixed via a ref that tracks latest activeTrade without triggering re-runs.
 */
import { createContext, useContext, useState, useEffect, useRef } from "react";
import { useWebSocket } from "./WebSocketContext";

const Ctx = createContext(null);

export function TradeProvider({ children }) {
  const { lastTick, lastExit } = useWebSocket();
  const [activeTrade, setActiveTrade] = useState(null);
  const [lastExitEv,  setLastExitEv]  = useState(null);
  const [livePnl,     setLivePnl]     = useState(null);
  const [livePrice,   setLivePrice]   = useState(null);

  // Ref keeps latest activeTrade accessible inside effects without causing extra deps
  const activeTradeRef = useRef(null);
  useEffect(() => { activeTradeRef.current = activeTrade; }, [activeTrade]);

  // ── On tick: update live price + pnl ───────────────────────────────────────
  useEffect(() => {
    if (!lastTick) return;

    // Filter to only the currently active trade's symbol
    if (activeTrade && lastTick.symbol !== activeTrade.symbol) return;

    setLivePrice(lastTick.price);
    if (lastTick.live_pnl != null) setLivePnl(lastTick.live_pnl);

    // Sync activeTrade from tick payload if backend carries one and we don't have one yet
    if (!activeTrade && lastTick.active_trade) {
      setActiveTrade(lastTick.active_trade);
    }
  }, [lastTick, activeTrade]);

  // ── On exit event ───────────────────────────────────────────────────────────
  // Uses activeTradeRef to avoid stale closure (no activeTrade in dep array)
  useEffect(() => {
    if (!lastExit) return;
    const current = activeTradeRef.current;
    const isForActiveTrade = current
      ? lastExit.symbol === current.symbol
      : lastExit.type === "exit";

    if (isForActiveTrade || lastExit.type === "exit") {
      setLastExitEv(lastExit);
      setActiveTrade(null);
      setLivePnl(null);
    }
  }, [lastExit]);

  const openTrade   = (trade) => setActiveTrade(trade);
  const clearTrade  = ()      => { setActiveTrade(null); setLivePnl(null); };
  const dismissExit = ()      => setLastExitEv(null);

  const forceClose = async (symbol, price) => {
    const res  = await fetch(`/api/trade/${encodeURIComponent(symbol)}?price=${price || 0}`, { method: "DELETE" });
    const data = await res.json();
    if (data.exit) { setLastExitEv(data.exit); clearTrade(); }
    return data.exit;
  };

  return (
    <Ctx.Provider value={{
      activeTrade, livePrice, livePnl, lastExitEv,
      openTrade, clearTrade, dismissExit, forceClose,
    }}>
      {children}
    </Ctx.Provider>
  );
}

export const useTrade = () => useContext(Ctx);