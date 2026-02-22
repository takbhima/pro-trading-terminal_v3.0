/**
 * App.jsx — React composition root
 * Mirrors main.py's role: wires all providers and top-level layout.
 * Each panel is a single-responsibility component.
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
            <Sidebar
              symbol={symbol}
              interval={interval}
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
