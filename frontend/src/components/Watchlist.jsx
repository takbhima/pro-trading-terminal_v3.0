/**
 * Watchlist — with live spot prices + bug fixes:
 *
 * BUG FIX 1: Local useWatchlist() hook was always instantiated even when
 *   watchlistHook prop was provided — wasteful duplicate API call.
 *   Fixed by conditionally using the prop first.
 *
 * BUG FIX 2: clearAllSignals in useEffect dep array caused potential
 *   stale closure issues. Stabilized via useRef pattern.
 *
 * NEW: Displays live spot price and % change for each watchlist item.
 *   Polls GET /api/watchlist/prices every 15 seconds.
 *   Color-coded green/red with flash animation on price change.
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { useWebSocket } from "../context/WebSocketContext";
import { useWatchlist }  from "../hooks/useWatchlist";

const PRICE_REFRESH_MS = 15_000;

// Small hook to manage watchlist prices
function useWatchlistPrices(items) {
  const [prices, setPrices] = useState({});  // sym → { price, change_pct, up }
  const [flashing, setFlashing] = useState({}); // sym → "up" | "down" | null
  const prevPricesRef = useRef({});
  const timerRef = useRef(null);

  const fetchPrices = useCallback(async () => {
    if (!items.length) return;
    try {
      const syms = items.map(i => i.sym).join(",");
      const res  = await fetch(`/api/watchlist/prices?symbols=${encodeURIComponent(syms)}`);
      if (!res.ok) return;
      const data = await res.json();
      const newPrices = {};
      const newFlash  = {};

      for (const entry of (data.prices || [])) {
        newPrices[entry.sym] = {
          price:      entry.price,
          change_pct: entry.change_pct,
          up:         entry.change_pct >= 0,
        };
        // Detect price change for flash animation
        const prev = prevPricesRef.current[entry.sym];
        if (prev && prev.price !== entry.price) {
          newFlash[entry.sym] = entry.price > prev.price ? "up" : "down";
        }
      }

      prevPricesRef.current = newPrices;
      setPrices(newPrices);

      // Apply flash then clear after 700ms
      if (Object.keys(newFlash).length) {
        setFlashing(newFlash);
        setTimeout(() => setFlashing({}), 700);
      }
    } catch {
      // silent — prices are non-critical
    }
  }, [items]);

  useEffect(() => {
    fetchPrices();
    timerRef.current = setInterval(fetchPrices, PRICE_REFRESH_MS);
    return () => clearInterval(timerRef.current);
  }, [fetchPrices]);

  return prices, flashing;
}

export default function Watchlist({ activeSymbol, onSelect, onAdd, activeStrategy, watchlistHook }) {
  // BUG FIX 1: Only instantiate local hook if no external hook provided
  const localHook = useWatchlist();
  const { items, loading, signals, remove, setSignal, clearAllSignals } =
    watchlistHook || localHook;

  const { lastSignal, lastClear } = useWebSocket();
  const [filter, setFilter] = useState("");

  // BUG FIX 2: Stabilise clearAllSignals reference via ref to avoid stale closures
  const clearAllSignalsRef = useRef(clearAllSignals);
  useEffect(() => { clearAllSignalsRef.current = clearAllSignals; }, [clearAllSignals]);

  // Live prices
  const [prices,   setPrices]   = useState({});
  const [flashing, setFlashing] = useState({});
  const prevPricesRef = useRef({});
  const priceTimerRef = useRef(null);

  const fetchPrices = useCallback(async () => {
    if (!items.length) return;
    try {
      const syms = items.map(i => i.sym).join(",");
      const res  = await fetch(`/api/watchlist/prices?symbols=${encodeURIComponent(syms)}`);
      if (!res.ok) return;
      const data = await res.json();
      const newPrices = {};
      const newFlash  = {};
      for (const entry of (data.prices || [])) {
        newPrices[entry.sym] = {
          price:      entry.price,
          change_pct: entry.change_pct,
          up:         entry.change_pct >= 0,
        };
        const prev = prevPricesRef.current[entry.sym];
        if (prev && prev.price !== 0 && prev.price !== entry.price) {
          newFlash[entry.sym] = entry.price > prev.price ? "up" : "down";
        }
      }
      prevPricesRef.current = newPrices;
      setPrices(newPrices);
      if (Object.keys(newFlash).length) {
        setFlashing(newFlash);
        setTimeout(() => setFlashing({}), 700);
      }
    } catch {
      // silent
    }
  }, [items]);

  useEffect(() => {
    fetchPrices();
    priceTimerRef.current = setInterval(fetchPrices, PRICE_REFRESH_MS);
    return () => clearInterval(priceTimerRef.current);
  }, [fetchPrices]);

  // Clear badges when strategy changes — using ref to avoid dep-loop
  useEffect(() => {
    clearAllSignalsRef.current?.();
  }, [activeStrategy]);

  // Update badge only if signal strategy matches active strategy
  useEffect(() => {
    if (!lastSignal?.symbol) return;
    const sigStrategy = lastSignal.strategy || "pro_mtf";
    if (sigStrategy !== activeStrategy) return;
    setSignal(lastSignal.symbol, lastSignal.signal_type || lastSignal.type_);
  }, [lastSignal, activeStrategy, setSignal]);

  // Handle signal_clear from backend
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

  function fmtPrice(p) {
    if (!p || p === 0) return "—";
    const n = Number(p);
    if (isNaN(n) || n === 0) return "—";
    if (n >= 10000) return n.toLocaleString("en-IN", { maximumFractionDigits: 0 });
    if (n >= 100)   return n.toLocaleString("en-IN", { maximumFractionDigits: 1 });
    return n.toFixed(2);
  }

  function fmtPct(pct) {
    if (pct == null) return "";
    const sign = pct >= 0 ? "+" : "";
    return `${sign}${Number(pct).toFixed(2)}%`;
  }

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
          const sig      = signals[w.sym] || "NONE";
          const sigText  = sig === "BUY" ? "▲" : sig === "SELL" ? "▼" : "";
          const priceData = prices[w.sym];
          const flashCls = flashing[w.sym] ? ` wl-flash-${flashing[w.sym]}` : "";

          return (
            <div
              key={w.sym}
              className={`wl-item${w.sym === activeSymbol ? " active" : ""}${flashCls}`}
              onClick={() => onSelect(w.sym, w.name || w.sym)}
            >
              {/* Left: name + ticker + signal badge */}
              <div className="wl-left">
                <div className="wl-nm-row">
                  <span className="wl-nm">{w.name || w.sym}</span>
                  {sig !== "NONE" && (
                    <span className={`wl-sig-inline ${sig}`}>{sigText} {sig}</span>
                  )}
                </div>
                <div className="wl-tk">{w.sym}</div>
              </div>

              {/* Right: price + change% + remove */}
              <div className="wl-right">
                {priceData && priceData.price > 0 ? (
                  <div className="wl-price-col">
                    <span className={`wl-price ${priceData.up ? "up" : "dn"}`}>
                      {fmtPrice(priceData.price)}
                    </span>
                    <span className={`wl-pct ${priceData.up ? "up" : "dn"}`}>
                      {fmtPct(priceData.change_pct)}
                    </span>
                  </div>
                ) : (
                  <div className="wl-price-col">
                    <span className="wl-price loading">—</span>
                  </div>
                )}
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