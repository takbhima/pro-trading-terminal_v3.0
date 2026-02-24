/**
 * WatchlistSignalsTab — "📡 Radar" tab
 * =====================================
 * Shows the latest signal for EVERY stock in the watchlist.
 * Auto-refreshes every 60 seconds. Live WS signals update cards instantly
 * with a 10-second pulse animation.
 * Click any card → jumps to that stock's chart (same as signal history cards).
 *
 * Fetches via GET /api/chartdata (existing endpoint, no backend changes needed).
 * Uses useWatchlist() which is already lifted to App.jsx.
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { useWatchlist }   from "../hooks/useWatchlist";
import { useWebSocket }   from "../context/WebSocketContext";
import { fmt }            from "../utils/utils";

const REFRESH_INTERVAL_MS = 60_000;  // 60 seconds

// ─── helpers ────────────────────────────────────────────────────────────────

function signalAge(time) {
  if (!time) return "";
  // time can be a unix int (intraday) or "YYYY-MM-DD" string (daily)
  const ts = typeof time === "number" ? time * 1000 : Date.parse(time + "T00:00:00");
  if (isNaN(ts)) return "";
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60)   return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

// Fetch latest signal for one symbol using the existing /api/chartdata endpoint
async function fetchLatestSignal(yahoo, strategy, requireMtf, signal) {
  const url =
    `/api/chartdata?symbol=${encodeURIComponent(yahoo)}` +
    `&interval=1d` +
    `&strategy=${strategy}` +
    (requireMtf ? "&require_mtf=1" : "");
  const res = await fetch(url, { signal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.latest_signal || null;   // null = no signal
}

// ─── Countdown sub-component ─────────────────────────────────────────────────
function Countdown({ nextRefresh, onRefresh }) {
  const [secs, setSecs] = useState(0);
  useEffect(() => {
    const id = setInterval(() => {
      const remaining = Math.max(0, Math.round((nextRefresh - Date.now()) / 1000));
      setSecs(remaining);
    }, 1000);
    return () => clearInterval(id);
  }, [nextRefresh]);

  return (
    <span className="radar-countdown-text">
      Refresh in {secs}s
      <button className="radar-refresh-btn" onClick={onRefresh} title="Refresh now">↻</button>
    </span>
  );
}

// ─── Individual signal card ───────────────────────────────────────────────────
function RadarCard({ entry, isLive, onJumpToSignal }) {
  const { symbol, signal, loading, error } = entry;
  const isBuy = signal?.type === "BUY";

  const handleClick = () => {
    if (!onJumpToSignal || !signal?.time) return;
    onJumpToSignal(signal.time, signal.signal_id || `${symbol.yahoo}_${signal.time}`, symbol.yahoo, symbol.label);
  };

  return (
    <div
      className={`radar-card${signal ? ` ${signal.type}` : ""}${isLive ? " live-pulse" : ""}${onJumpToSignal && signal ? " clickable" : ""}`}
      onClick={signal ? handleClick : undefined}
      title={signal && onJumpToSignal ? "Click to jump to this stock's chart" : undefined}
    >
      {/* Header row */}
      <div className="radar-card-header">
        <span className="radar-sym">{symbol.label}</span>
        <span className="radar-ticker">{symbol.yahoo}</span>
        {isLive && <span className="radar-live-badge">● LIVE</span>}
        {signal && (
          <span className={`radar-sig-type ${signal.type}`}>
            {isBuy ? "▲ BUY" : "▼ SELL"}
          </span>
        )}
      </div>

      {/* Body */}
      {loading && (
        <div className="radar-card-body muted">Loading…</div>
      )}
      {error && !loading && (
        <div className="radar-card-body muted">⚠ {error}</div>
      )}
      {!loading && !error && !signal && (
        <div className="radar-card-body muted">No signal on 1D</div>
      )}
      {!loading && !error && signal && (
        <div className="radar-card-body">
          <div className="radar-prices">
            <div className="radar-price-row">
              <span className="rp-lbl">Entry</span>
              <span className="rp-val entry">{fmt(signal.price)}</span>
            </div>
            <div className="radar-price-row">
              <span className="rp-lbl">SL</span>
              <span className="rp-val sl">{fmt(signal.sl)}</span>
            </div>
            <div className="radar-price-row">
              <span className="rp-lbl">TP</span>
              <span className="rp-val tp">{fmt(signal.tp)}</span>
            </div>
          </div>
          <div className="radar-meta">
            <span className="radar-strategy-badge">{signal.strategy}</span>
            {signal.target_time && (
              <span className="radar-target-time">⏱ {signal.target_time}</span>
            )}
            <span className="radar-age">{signalAge(signal.time)}</span>
          </div>
          {onJumpToSignal && (
            <div className="radar-jump-hint">↗ Jump to chart</div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function WatchlistSignalsTab({ strategy, requireMtf, onJumpToSignal }) {
  const { items }      = useWatchlist();
  const { lastSignal } = useWebSocket();

  // signalMap: yahoo → { symbol: {yahoo, label}, signal: obj|null, loading, error }
  const [signalMap,  setSignalMap]  = useState(new Map());
  const [liveYahoos, setLiveYahoos] = useState(new Set());   // recently updated via WS
  const [nextRefresh, setNextRefresh] = useState(Date.now() + REFRESH_INTERVAL_MS);
  const abortRefs   = useRef({});   // yahoo → AbortController
  const liveTimers  = useRef({});   // yahoo → timeout id

  // ── Fetch one symbol ──────────────────────────────────────────────────────
  const fetchOne = useCallback(async (sym) => {
    // Abort any in-flight request for this symbol
    abortRefs.current[sym.yahoo]?.abort();
    const ctrl = new AbortController();
    abortRefs.current[sym.yahoo] = ctrl;

    setSignalMap(prev => {
      const next = new Map(prev);
      const cur  = next.get(sym.yahoo) || {};
      next.set(sym.yahoo, { symbol: sym, signal: cur.signal || null, loading: true, error: null });
      return next;
    });

    try {
      const signal = await fetchLatestSignal(sym.yahoo, strategy, requireMtf, ctrl.signal);
      if (ctrl.signal.aborted) return;
      setSignalMap(prev => {
        const next = new Map(prev);
        next.set(sym.yahoo, { symbol: sym, signal, loading: false, error: null });
        return next;
      });
    } catch (e) {
      if (e.name === "AbortError") return;
      setSignalMap(prev => {
        const next = new Map(prev);
        next.set(sym.yahoo, { symbol: sym, signal: null, loading: false, error: e.message });
        return next;
      });
    }
  }, [strategy, requireMtf]);

  // ── Fetch all watchlist symbols ───────────────────────────────────────────
  const fetchAll = useCallback((watchlistItems) => {
    watchlistItems.forEach(item => {
      fetchOne({ yahoo: item.sym, label: item.name || item.sym });
    });
    setNextRefresh(Date.now() + REFRESH_INTERVAL_MS);
  }, [fetchOne]);

  // ── Initial load + watchlist change ──────────────────────────────────────
  const prevItemsRef = useRef([]);
  useEffect(() => {
    if (!items.length) return;
    // Only re-fetch if watchlist actually changed
    const prevKeys = prevItemsRef.current.map(i => i.sym).join(",");
    const nextKeys = items.map(i => i.sym).join(",");
    if (prevKeys === nextKeys) return;
    prevItemsRef.current = items;

    // Remove entries for stocks no longer in watchlist
    setSignalMap(prev => {
      const next = new Map();
      items.forEach(item => {
        if (prev.has(item.sym)) next.set(item.sym, prev.get(item.sym));
      });
      return next;
    });

    fetchAll(items);
  }, [items, fetchAll]);

  // ── Strategy / MTF change → re-fetch all ─────────────────────────────────
  const prevStratRef = useRef(strategy);
  const prevMtfRef   = useRef(requireMtf);
  useEffect(() => {
    if (prevStratRef.current === strategy && prevMtfRef.current === requireMtf) return;
    prevStratRef.current = strategy;
    prevMtfRef.current   = requireMtf;
    if (items.length) fetchAll(items);
  }, [strategy, requireMtf, items, fetchAll]);

  // ── Auto-refresh timer ────────────────────────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => {
      if (items.length) fetchAll(items);
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [items, fetchAll]);

  // ── Live WS signal → update matching card instantly ───────────────────────
  useEffect(() => {
    if (!lastSignal) return;
    const sigYahoo    = lastSignal.symbol;
    const sigStrategy = lastSignal.strategy || "pro_mtf";
    if (!sigYahoo || sigStrategy !== strategy) return;

    // Only update if this symbol is in our watchlist
    setSignalMap(prev => {
      if (!prev.has(sigYahoo)) return prev;
      const cur  = prev.get(sigYahoo);
      const next = new Map(prev);
      next.set(sigYahoo, {
        ...cur,
        signal: {
          type:          lastSignal.signal_type || lastSignal.type,
          price:         lastSignal.price,
          sl:            lastSignal.sl,
          tp:            lastSignal.tp,
          rsi:           lastSignal.rsi,
          atr:           lastSignal.atr,
          confidence:    lastSignal.confidence,
          strategy:      lastSignal.strategy,
          time:          lastSignal.time,
          target_time:   lastSignal.target_time,
          signal_id:     lastSignal.signal_id,
        },
        loading: false,
        error:   null,
      });
      return next;
    });

    // Mark as live for 10 seconds
    setLiveYahoos(prev => new Set([...prev, sigYahoo]));
    clearTimeout(liveTimers.current[sigYahoo]);
    liveTimers.current[sigYahoo] = setTimeout(() => {
      setLiveYahoos(prev => {
        const next = new Set(prev);
        next.delete(sigYahoo);
        return next;
      });
    }, 10_000);
  }, [lastSignal, strategy]);

  // ── Cleanup on unmount ────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      Object.values(abortRefs.current).forEach(c => c.abort());
      Object.values(liveTimers.current).forEach(clearTimeout);
    };
  }, []);

  // ── Sorted entries: live first → BUY → SELL → no signal, then by recency ─
  const entries = [...signalMap.values()].sort((a, b) => {
    const aLive = liveYahoos.has(a.symbol.yahoo) ? 1 : 0;
    const bLive = liveYahoos.has(b.symbol.yahoo) ? 1 : 0;
    if (aLive !== bLive) return bLive - aLive;

    const aHas = a.signal ? 1 : 0;
    const bHas = b.signal ? 1 : 0;
    if (aHas !== bHas) return bHas - aHas;

    // Both have signals — BUY before SELL
    if (a.signal && b.signal && a.signal.type !== b.signal.type) {
      return a.signal.type === "BUY" ? -1 : 1;
    }
    return 0;
  });

  // ── Summary counts ────────────────────────────────────────────────────────
  const total   = entries.length;
  const buyCount  = entries.filter(e => e.signal?.type === "BUY").length;
  const sellCount = entries.filter(e => e.signal?.type === "SELL").length;
  const liveCount = liveYahoos.size;

  return (
    <div className="radar-tab">
      {/* Summary bar */}
      <div className="radar-summary-bar">
        <span className="radar-stat">{total} stocks</span>
        <span className="radar-stat buy">{buyCount} BUY</span>
        <span className="radar-stat sell">{sellCount} SELL</span>
        {liveCount > 0 && (
          <span className="radar-stat live">{liveCount} LIVE</span>
        )}
        <div className="radar-countdown">
          <Countdown nextRefresh={nextRefresh} onRefresh={() => fetchAll(items)} />
        </div>
      </div>

      {/* Cards */}
      <div className="radar-grid">
        {entries.length === 0 && (
          <div className="radar-empty">
            <div style={{ fontSize: 22, marginBottom: 6 }}>📡</div>
            Add stocks to your watchlist<br />to see signals here
          </div>
        )}
        {entries.map(entry => (
          <RadarCard
            key={entry.symbol.yahoo}
            entry={entry}
            isLive={liveYahoos.has(entry.symbol.yahoo)}
            onJumpToSignal={onJumpToSignal}
          />
        ))}
      </div>
    </div>
  );
}
