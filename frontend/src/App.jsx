/**
 * App.jsx — React composition root
 * Mirrors main.py's role: wires all providers and top-level layout.
 * Each panel is a single-responsibility component.
 *
 * BUG FIX: `strategy` state is now passed to <Sidebar> so it reaches
 * <SignalTab> and useChartData fetches the correct strategy's signals.
 * Previously Sidebar received no strategy prop, so SignalTab fell back
 * to the hardcoded "pro_mtf" regardless of user selection.
 */
import { useState, useCallback } from "react";
import { WebSocketProvider } from "./context/WebSocketContext";
import { TradeProvider }     from "./context/TradeContext";
import TopBar                from "./components/TopBar";
import StrategyBar           from "./components/StrategyBar";
import Watchlist             from "./components/Watchlist";
import ChartPanel            from "./components/ChartPanel";
import Sidebar               from "./components/Sidebar";
import AddSymbolModal        from "./components/AddSymbolModal";

export default function App() {
  const [symbol,   setSymbol]   = useState({ yahoo: "^BSESN", label: "SENSEX" });
  const [interval, setInterval] = useState("1d");
  const [strategy, setStrategy] = useState("pro_mtf");
  const [modal,    setModal]    = useState(false);

  const handleScan = useCallback((yahoo, label) => {
    setSymbol({ yahoo, label });
  }, []);

  return (
    <WebSocketProvider>
      <TradeProvider>
        <div className="app-shell">
          <TopBar
            symbol={symbol}
            interval={interval}
            onScan={handleScan}
            onIntervalChange={setInterval}
          />
          <StrategyBar
            activeStrategy={strategy}
            onStrategyChange={setStrategy}
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
            />
            {/* FIX: strategy prop added — was missing, causing SignalTab
                to always use "pro_mtf" regardless of active strategy */}
            <Sidebar
              symbol={symbol}
              interval={interval}
              strategy={strategy}
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
      </TradeProvider>
    </WebSocketProvider>
  );
}
