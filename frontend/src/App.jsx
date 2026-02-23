/**
 * App.jsx — FIX: strategy is now passed to WebSocket subscribe so the
 * backend scans using the correct strategy per client.
 * Also clears watchlist signal badges on strategy/interval/symbol change.
 * NEW: jumpToSignal state bridges SignalTab → ChartPanel so clicking a
 * signal history card scrolls the chart to that signal's timestamp.
 */
import { useState, useCallback, useEffect } from "react";
import { WebSocketProvider } from "./context/WebSocketContext";
import { TradeProvider }     from "./context/TradeContext";
import TopBar                from "./components/TopBar";
import StrategyBar           from "./components/StrategyBar";
import Watchlist             from "./components/Watchlist";
import ChartPanel            from "./components/ChartPanel";
import Sidebar               from "./components/Sidebar";
import AddSymbolModal        from "./components/AddSymbolModal";
import NotificationBanner, { useSignalAudio } from "./components/NotificationBanner";
import { useWebSocket }      from "./context/WebSocketContext";

function AppInner() {
  const [symbol,        setSymbol]        = useState({ yahoo: "^BSESN", label: "SENSEX" });
  const [interval,      setInterval]      = useState("1d");
  const [strategy,      setStrategy]      = useState("pro_mtf");
  const [mtfEnabled,    setMtfEnabled]    = useState(false);
  const [modal,         setModal]         = useState(false);
  const [fetchKey,      setFetchKey]      = useState(0);
  // jumpToSignal: { time, signal_id } — set by SignalTab, consumed by ChartPanel
  const [jumpToSignal,  setJumpToSignal]  = useState(null);

  const { subscribe } = useWebSocket();

  useSignalAudio();

  // FIX: re-subscribe with strategy whenever any of these change
  useEffect(() => {
    subscribe(symbol.yahoo, interval, strategy);
  }, [symbol.yahoo, interval, strategy, subscribe]);

  const handleScan = useCallback((yahoo, label) => {
    setSymbol({ yahoo, label });
    setFetchKey(k => k + 1);
    setJumpToSignal(null);  // clear jump target on symbol change
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

  // Called by SignalTab when user clicks a signal history card
  const handleJumpToSignal = useCallback((time, signal_id) => {
    setJumpToSignal({ time, signal_id, _at: Date.now() });
  }, []);

  return (
    <div className="app-shell">
      <NotificationBanner />

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
        {/* FIX: pass strategy so Watchlist can clear stale badges on switch */}
        <Watchlist
          activeSymbol={symbol.yahoo}
          onSelect={handleScan}
          onAdd={() => setModal(true)}
          activeStrategy={strategy}
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
