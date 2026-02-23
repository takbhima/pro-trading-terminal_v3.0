/**
 * App.jsx — Composition root.
 * NEW: MarketTicker added above TopBar for live SENSEX / Nifty / Bank Nifty strip.
 */
import { useState, useCallback, useEffect } from "react";
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

function AppInner() {
  const [symbol,       setSymbol]       = useState({ yahoo: "^BSESN", label: "SENSEX" });
  const [interval,     setInterval]     = useState("1d");
  const [strategy,     setStrategy]     = useState("pro_mtf");
  const [mtfEnabled,   setMtfEnabled]   = useState(false);
  const [modal,        setModal]        = useState(false);
  const [fetchKey,     setFetchKey]     = useState(0);
  const [jumpToSignal, setJumpToSignal] = useState(null);

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

  const handleJumpToSignal = useCallback((time, signal_id) => {
    setJumpToSignal({ time, signal_id, _at: Date.now() });
  }, []);

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