/**
 * Watchlist — Single Responsibility: display + manage watchlist items.
 */
import { useState, useEffect } from "react";
import { useWebSocket } from "../context/WebSocketContext";
import { useWatchlist }  from "../hooks/useWatchlist";

export default function Watchlist({ activeSymbol, onSelect, onAdd }) {
  const { items, loading, signals, remove, setSignal } = useWatchlist();
  const { lastSignal } = useWebSocket();
  const [filter, setFilter] = useState("");

  // Update signal badge when WS signal arrives
  useEffect(() => {
    if (lastSignal?.symbol) {
      // BUG FIX: WS sends signal_type for the direction, type is the WS message type
      setSignal(lastSignal.symbol, lastSignal.signal_type || lastSignal.type_);
    }
  }, [lastSignal, setSignal]);

  const filtered = items.filter(
    (w) =>
      !filter ||
      w.sym.toLowerCase().includes(filter.toLowerCase()) ||
      (w.name || "").toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <aside className="wl-panel">
      <div className="wl-hdr">
        <span>📋 Watchlist</span>
        <button className="wl-add-btn" onClick={onAdd}>+ Add</button>
      </div>
      <div className="wl-search-wrap">
        <input
          className="wl-search"
          placeholder="Filter…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
      </div>

      <div className="wl-items">
        {loading && <div className="wl-empty">Loading…</div>}
        {!loading && !filtered.length && <div className="wl-empty">No items</div>}
        {filtered.map((w) => {
          const sig     = signals[w.sym] || "NONE";
          const sigText = sig === "BUY" ? "▲ BUY" : sig === "SELL" ? "▼ SELL" : "—";
          return (
            <div
              key={w.sym}
              className={`wl-item${w.sym === activeSymbol ? " active" : ""}`}
              onClick={() => onSelect(w.sym, w.name || w.sym)}
            >
              <div>
                <div className="wl-nm">{w.name || w.sym}</div>
                <div className="wl-tk">{w.sym}</div>
              </div>
              <div className="wl-right">
                <span className={`wl-sig ${sig}`}>{sigText}</span>
                <button
                  className="wl-rm"
                  onClick={(e) => { e.stopPropagation(); remove(w.sym); }}
                  title="Remove"
                >
                  ✕
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </aside>
  );
}
