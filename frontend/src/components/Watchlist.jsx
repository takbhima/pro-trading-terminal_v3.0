/**
 * Watchlist — FIX:
 *  1. Clears ALL signal badges when activeStrategy prop changes.
 *  2. Handles "signal_clear" WS messages from backend (no signal on this strategy).
 *  3. Only accepts signal badge updates whose strategy matches activeStrategy.
 *  4. FIX (new): Accepts optional `watchlistHook` prop from App.jsx so that
 *     when the parent calls watchlistHook.reload() after adding a symbol, the
 *     same hook instance is used and the list updates immediately without refresh.
 */
import { useState, useEffect } from "react";
import { useWebSocket } from "../context/WebSocketContext";
import { useWatchlist }  from "../hooks/useWatchlist";

export default function Watchlist({ activeSymbol, onSelect, onAdd, activeStrategy, watchlistHook }) {
  // FIX-2: Use the shared hook instance from App if provided, otherwise create a local one.
  // Using a shared instance means App.reload() and Watchlist see the same state.
  const localHook = useWatchlist();
  const { items, loading, signals, remove, setSignal, clearAllSignals } =
    watchlistHook || localHook;

  const { lastSignal, lastClear } = useWebSocket();
  const [filter, setFilter] = useState("");

  // FIX-1: whenever strategy changes, wipe all stale signal badges immediately
  useEffect(() => {
    clearAllSignals();
  }, [activeStrategy, clearAllSignals]);

  // FIX-2: update badge only if signal strategy matches the currently active strategy
  useEffect(() => {
    if (!lastSignal?.symbol) return;
    const sigStrategy = lastSignal.strategy || "pro_mtf";
    if (sigStrategy !== activeStrategy) return;  // ignore stale strategy signals
    setSignal(lastSignal.symbol, lastSignal.signal_type || lastSignal.type_);
  }, [lastSignal, activeStrategy, setSignal]);

  // FIX-2: handle signal_clear — backend says no signal for this sym on current strategy
  useEffect(() => {
    if (!lastClear?.symbol) return;
    const clearStrategy = lastClear.strategy || "pro_mtf";
    if (clearStrategy !== activeStrategy) return;
    setSignal(lastClear.symbol, "NONE");
  }, [lastClear, activeStrategy, setSignal]);

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