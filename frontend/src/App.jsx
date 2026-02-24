/**
 * App.jsx — Composition root.
 * NEW: MarketTicker added above TopBar for live SENSEX / Nifty / Bank Nifty strip.
 *
 * FIX-1: handleJumpToSignal now accepts (time, signal_id, symbolYahoo, symbolLabel).
 *   When a signal from a different stock is clicked in history, the active symbol
 *   is switched first, then the chart scrolls to that signal's timestamp.
 *   A small delay ensures the chart has loaded before the scroll is attempted.
 *
 * FIX-2: onAdd in AddSymbolModal now reloads the watchlist items so the new
 *   stock appears immediately without a page refresh.
 */
import { useState, useCallback, useEffect, useRef } from "react";
import { WebSocketProvider } from "./context/WebSocketContext";
import { TradeProvider }     from "./context/TradeContext";
import MarketTicker          from "./components/MarketTicker";
import TopBar                from "./components/TopBar";
import StrategyBar           from "./components/StrategyBar";
import Watchlist             from "./components/Watchlist";
import ChartPanel            from "./components/ChartPanel";
import Sidebar               from "./components/Sidebar";
import AddSymbolModal        from "./components/AddSymbolModal";
import NotificationBanner, { useSignalAudio } from "./components/NotificationBanner";
import { useWebSocket }      from "./context/WebSocketContext";
import { useWatchlist }      from "./hooks/useWatchlist";

function AppInner() {
  const [symbol,       setSymbol]       = useState({ yahoo: "^BSESN", label: "SENSEX" });
  const [interval,     setInterval]     = useState("1d");
  const [strategy,     setStrategy]     = useState("pro_mtf");
  const [mtfEnabled,   setMtfEnabled]   = useState(false);
  const [modal,        setModal]        = useState(false);
  const [fetchKey,     setFetchKey]     = useState(0);
  const [jumpToSignal, setJumpToSignal] = useState(null);

  // FIX-2: Lift watchlist state up so AddSymbolModal can trigger a reload
  const watchlistHook = useWatchlist();

  const { subscribe } = useWebSocket();

  useSignalAudio();

  useEffect(() => {
    subscribe(symbol.yahoo, interval, strategy);
  }, [symbol.yahoo, interval, strategy, subscribe]);

  const handleScan = useCallback((yahoo, label) => {
    setSymbol({ yahoo, label });
    setFetchKey(k => k + 1);
    setJumpToSignal(null);
  }, []);

  const handleIntervalChange = useCallback((iv) => {
    setInterval(iv);
    setFetchKey(k => k + 1);
    setJumpToSignal(null);
  }, []);

  const handleStrategyChange = useCallback((strat) => {
    setStrategy(strat);
    setFetchKey(k => k + 1);
    setJumpToSignal(null);
  }, []);

  const handleMtfToggle = useCallback(() => {
    const next = !mtfEnabled;
    setMtfEnabled(next);
    setFetchKey(k => k + 1);
    fetch(`/api/settings/mtf?enabled=${next}`, { method: "PATCH" }).catch(() => {});
  }, [mtfEnabled]);

  // FIX-1: handleJumpToSignal now accepts the signal's stock symbol.
  // If it's different from the currently active symbol, we switch the chart
  // to that stock first, then set the scroll target.
  // We use a pendingJumpRef to store the jump target while the chart loads.
  const pendingJumpRef = useRef(null);

  const handleJumpToSignal = useCallback((time, signal_id, signalYahoo, signalLabel) => {
    const targetYahoo = signalYahoo || symbol.yahoo;
    const targetLabel = signalLabel || symbol.label;

    if (targetYahoo !== symbol.yahoo) {
      // Switch to the signal's stock — store jump target to apply after load
      pendingJumpRef.current = { time, signal_id };
      setSymbol({ yahoo: targetYahoo, label: targetLabel });
      setFetchKey(k => k + 1);
      setJumpToSignal(null); // clear old jump first
    } else {
      // Same stock — just scroll
      pendingJumpRef.current = null;
      setJumpToSignal({ time, signal_id, _at: Date.now() });
    }
  }, [symbol.yahoo, symbol.label]);

  // After a symbol switch triggered by handleJumpToSignal, apply the pending jump
  // once the new fetchKey has caused the chart to start loading.
  // We delay slightly to allow the chart to receive new data.
  useEffect(() => {
    if (!pendingJumpRef.current) return;
    const { time, signal_id } = pendingJumpRef.current;
    pendingJumpRef.current = null;

    // Delay to let the chart data fetch complete (~1.5s is usually enough)
    const timer = setTimeout(() => {
      setJumpToSignal({ time, signal_id, _at: Date.now() });
    }, 1500);

    return () => clearTimeout(timer);
  }, [fetchKey]); // re-run when fetchKey changes (i.e. when symbol switched)

  return (
    <div className="app-shell">
      <NotificationBanner />
      <MarketTicker />
      <TopBar
        symbol={symbol}
        interval={interval}
        strategy={strategy}
        onScan={handleScan}
        onIntervalChange={handleIntervalChange}
      />
      <StrategyBar
        activeStrategy={strategy}
        onStrategyChange={handleStrategyChange}
        mtfEnabled={mtfEnabled}
        onMtfToggle={handleMtfToggle}
      />
      <div className="main-grid">
        {/* FIX-2: pass watchlistHook so Watchlist uses the shared instance */}
        <Watchlist
          activeSymbol={symbol.yahoo}
          onSelect={handleScan}
          onAdd={() => setModal(true)}
          activeStrategy={strategy}
          watchlistHook={watchlistHook}
        />
        <ChartPanel
          symbol={symbol}
          interval={interval}
          strategy={strategy}
          requireMtf={mtfEnabled}
          fetchKey={fetchKey}
          jumpToSignal={jumpToSignal}
        />
        <Sidebar
          symbol={symbol}
          interval={interval}
          strategy={strategy}
          requireMtf={mtfEnabled}
          fetchKey={fetchKey}
          onJumpToSignal={handleJumpToSignal}
        />
      </div>
      {modal && (
        <AddSymbolModal
          onClose={() => setModal(false)}
          onAdd={(yahoo, label) => {
            setModal(false);
            // FIX-2: reload the watchlist so the new item appears immediately
            watchlistHook.reload();
            handleScan(yahoo, label);
          }}
        />
      )}
    </div>
  );
}

export default function App() {
  return (
    <WebSocketProvider>
      <TradeProvider>
        <AppInner />
      </TradeProvider>
    </WebSocketProvider>
  );
}