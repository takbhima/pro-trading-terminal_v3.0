/**
 * TopBar — FIX: subscribe now passes strategy so the backend uses the
 * correct strategy when scanning watchlist signals for this client.
 * strategy prop added; subscribe call updated.
 */
import { useState, useEffect } from "react";
import { useWebSocket } from "../context/WebSocketContext";
import { fmt } from "../utils/utils";

const TIMEFRAMES = ["1m", "3m", "5m", "15m", "1h", "1d", "1wk"];
const DEFAULT_TF = "1d";

const MARKETS = ["NSE", "NYSE", "NASDAQ", "LSE"];

export default function TopBar({ symbol, interval, strategy, onScan, onIntervalChange }) {
  const { status, lastTick, subscribe } = useWebSocket();
  const [input, setInput] = useState(symbol.yahoo);
  const [curTF,  setCurTF] = useState(interval || DEFAULT_TF);

  useEffect(() => { setInput(symbol.yahoo); }, [symbol.yahoo]);

  // FIX: re-subscribe whenever symbol, interval, OR strategy changes
  useEffect(() => {
    subscribe(symbol.yahoo, curTF, strategy);
  }, [symbol.yahoo, curTF, strategy, subscribe]);

  const handleScan = () => {
    const raw = input.trim().toUpperCase();
    if (!raw) return;
    onScan(raw, raw);
  };

  const handleTF = (tf) => {
    setCurTF(tf);
    onIntervalChange(tf);
  };

  const tick = lastTick?.symbol === symbol.yahoo ? lastTick : null;
  const tickUp = tick && tick.change >= 0;

  return (
    <header className="topbar">
      <div className="logo">
        <span className="logo-dot" />
        PRO TERMINAL
      </div>

      <div className="scan-row">
        <input
          className="sym-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleScan()}
          placeholder="AAPL · RELIANCE.NS · ^NSEI · BTC-USD"
        />
        <button className="scan-btn" onClick={handleScan}>▶ Scan</button>
      </div>

      <div className="tf-wrap">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf}
            className={`tf-btn${curTF === tf ? " active" : ""}`}
            onClick={() => handleTF(tf)}
          >
            {tf}
          </button>
        ))}
      </div>

      <div className="topbar-right">
        {tick && (
          <div className="live-tick">
            <span className="tick-sym">{symbol.label}</span>
            <span className="tick-price">{fmt(tick.price)}</span>
            <span className={`tick-chg ${tickUp ? "up" : "dn"}`}>
              {tickUp ? "▲" : "▼"} {Math.abs(tick.change_pct).toFixed(2)}%
            </span>
          </div>
        )}

        <div className="conn-status">
          <span className={`status-dot${status.connected ? " live" : ""}`} />
          <span className="status-lbl">{status.label}</span>
        </div>

        <div className="mkt-badges">
          {MARKETS.map((m) => {
            const on = status.openMarkets.includes(m);
            return (
              <span key={m} className={`mkt-badge ${on ? "open" : "closed"}`}>{m}</span>
            );
          })}
        </div>
      </div>
    </header>
  );
}
