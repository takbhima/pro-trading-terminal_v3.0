/**
 * App.jsx — React composition root (v4)
 *
 * New in v4:
 *  E4 — mtfEnabled state lifted here so both StrategyBar and ChartPanel/useChartData
 *       can share it. StrategyBar renders the MTF toggle; useChartData passes it
 *       as a query param to /api/chartdata?require_mtf=1.
 *  E5 — NotificationBanner rendered at top level; asks for permission once.
 *       useSignalAudio hook wired here to play beep on every signal.
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

// Inner component so hooks can access WebSocketContext
function AppInner() {
  const [symbol,     setSymbol]     = useState({ yahoo: "^BSESN", label: "SENSEX" });
  const [interval,   setInterval]   = useState("1d");
  const [strategy,   setStrategy]   = useState("pro_mtf");
  const [mtfEnabled, setMtfEnabled] = useState(false);  // E4
  const [modal,      setModal]      = useState(false);
  // fetchKey forces useChartData to re-fetch even if other deps haven't changed.
  // Incremented on every strategy/interval/symbol/mtf change to bust any caching.
  const [fetchKey,   setFetchKey]   = useState(0);

  // E5: play beep on signal
  useSignalAudio();

  const handleScan = useCallback((yahoo, label) => {
    setSymbol({ yahoo, label });
    setFetchKey(k => k + 1);
  }, []);

  const handleIntervalChange = useCallback((iv) => {
    setInterval(iv);
    setFetchKey(k => k + 1);
  }, []);

  const handleStrategyChange = useCallback((strat) => {
    setStrategy(strat);
    setFetchKey(k => k + 1);
  }, []);

  const handleMtfToggle = useCallback(() => {
    const next = !mtfEnabled;
    setMtfEnabled(next);
    setFetchKey(k => k + 1);
    // Sync to backend so watchlist scan also respects MTF setting
    fetch(`/api/settings/mtf?enabled=${next}`, { method: "PATCH" }).catch(() => {});
  }, [mtfEnabled]);

  return (
    <div className="app-shell">
      {/* E5: Notification permission banner */}
      <NotificationBanner />

      <TopBar
        symbol={symbol}
        interval={interval}
        onScan={handleScan}
        onIntervalChange={handleIntervalChange}
      />
      <StrategyBar
        activeStrategy={strategy}
        onStrategyChange={handleStrategyChange}
        mtfEnabled={mtfEnabled}      // E4
        onMtfToggle={handleMtfToggle} // E4
      />
      <div className="main-grid">
        <Watchlist
          activeSymbol={symbol.yahoo}
          onSelect={handleScan}
          onAdd={() => setModal(true)}
        />
        <ChartPanel
          symbol={symbol}
          interval={interval}
          strategy={strategy}
          requireMtf={mtfEnabled}
          fetchKey={fetchKey}
        />
        <Sidebar
          symbol={symbol}
          interval={interval}
          strategy={strategy}
          requireMtf={mtfEnabled}
          fetchKey={fetchKey}
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
