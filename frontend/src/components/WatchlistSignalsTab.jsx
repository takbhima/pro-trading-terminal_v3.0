/**
 * WatchlistSignalsTab — "📡 Radar" tab
 * =====================================
 * Shows the latest signal for EVERY stock in the watchlist.
 * Auto-refreshes every 60 seconds. Live WS signals update cards instantly
 * with a 10-second pulse animation.
 * Click any card → jumps to that stock's chart.
 *
 * FIXES applied in this version:
 *
 * 1. Hardcoded `interval=1d` — now accepts `interval` prop so Radar matches
 *    whatever timeframe is active on the chart (1m, 5m, 1d, etc.).
 *    Root cause of the original bug: Radar always showed stale 1D signals
 *    even when the chart was on 1m.
 *
 * 2. Missing prop wiring — Sidebar.jsx must pass `interval` down; see
 *    accompanying Sidebar.jsx fix.
 *
 * 3. WebSocket real-time update — live signals (from WS) were always
 *    accepted regardless of interval. Now filtered: only accepted
 *    if lastSignal.interval matches the current interval prop.
 *
 * 4. Double-fetch on strategy/interval change — prevStratRef + prevMtfRef
 *    was missing interval. Fixed with a single unified prevConfigRef.
 *
 * 5. Stale closure in fetchOne — fetchOne captured strategy/requireMtf at
 *    creation time. Now uses refs so always reads current values without
 *    needing to re-create fetchAll on every prop change.
 *
 * 6. "No signal" text updated for interval — "No signal on 1D" was
 *    hardcoded; now shows the actual interval.
 */
import "./WatchlistSignalsTab.css";
import { useState, useEffect, useRef, useCallback } from "react";
import { useWatchlist }   from "../hooks/useWatchlist";
import { useWebSocket }   from "../context/WebSocketContext";
import { fmt }            from "../utils/utils";

const REFRESH_INTERVAL_MS = 60_000; // 60 seconds

// ─── helpers ────────────────────────────────────────────────────────────────

function signalAge(time) {
  if (!time) return "";
  const ts = typeof time === "number" ? time * 1000 : Date.parse(time + "T00:00:00");
  if (isNaN(ts)) return "";
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60)    return `${s}s ago`;
  if (s < 3600)  return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

// FIX #1: accepts `interval` param instead of hardcoding "1d"
async function fetchLatestSignal(yahoo, interval, strategy, requireMtf, abortSignal) {
  const url =
    `/api/chartdata?symbol=${encodeURIComponent(yahoo)}` +
    `&interval=${encodeURIComponent(interval)}` +
    `&strategy=${strategy}` +
    (requireMtf ? "&require_mtf=1" : "");
  const res = await fetch(url, { signal: abortSignal });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  return data.latest_signal || null;
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
// FIX #6: receives interval so "No signal" shows the correct timeframe label
function RadarCard({ entry, isLive, onJumpToSignal, interval }) {
  const { symbol, signal, loading, error } = entry;
  const isBuy = signal?.type === "BUY";

  const handleClick = () => {
    if (!onJumpToSignal || !signal?.time) return;
    onJumpToSignal(
      signal.time,
      signal.signal_id || `${symbol.yahoo}_${signal.time}`,
      symbol.yahoo,
      symbol.label,
    );
  };

  return (
    <div
      className={`radar-card${signal ? ` ${signal.type}` : ""}${isLive ? " live-pulse" : ""}${onJumpToSignal && signal ? " clickable" : ""}`}
      onClick={signal ? handleClick : undefined}
      title={signal && onJumpToSignal ? "Click to jump to this stock's chart" : undefined}
    >
      {/* Header */}
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
        // FIX #6: show actual interval instead of hardcoded "1D"
        <div className="radar-card-body muted">No signal on {interval.toUpperCase()}</div>
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
export default function WatchlistSignalsTab({
  interval = "1d",   // FIX #1: prop instead of hardcoded "1d"
  strategy,
  requireMtf,
  onJumpToSignal,
}) {
  const { items }      = useWatchlist();
  const { lastSignal } = useWebSocket();

  // signalMap: yahoo → { symbol, signal, loading, error }
  const [signalMap,   setSignalMap]   = useState(new Map());
  const [liveYahoos,  setLiveYahoos]  = useState(new Set());
  const [nextRefresh, setNextRefresh] = useState(Date.now() + REFRESH_INTERVAL_MS);
  const abortRefs  = useRef({}); // yahoo → AbortController
  const liveTimers = useRef({}); // yahoo → timeout id

  // FIX #5: stable refs so fetchOne never goes stale without needing recreation
  const strategyRef   = useRef(strategy);
  const requireMtfRef = useRef(requireMtf);
  const intervalRef   = useRef(interval);
  useEffect(() => { strategyRef.current   = strategy;   }, [strategy]);
  useEffect(() => { requireMtfRef.current = requireMtf; }, [requireMtf]);
  useEffect(() => { intervalRef.current   = interval;   }, [interval]);

  // ── Fetch one symbol ──────────────────────────────────────────────────────
  // FIX #5: stable callback — reads current config from refs, no deps needed
  const fetchOne = useCallback((sym) => {
    abortRefs.current[sym.yahoo]?.abort();
    const ctrl = new AbortController();
    abortRefs.current[sym.yahoo] = ctrl;

    setSignalMap(prev => {
      const next = new Map(prev);
      const cur  = next.get(sym.yahoo) || {};
      next.set(sym.yahoo, { symbol: sym, signal: cur.signal || null, loading: true, error: null });
      return next;
    });

    fetchLatestSignal(
      sym.yahoo,
      intervalRef.current,    // FIX #1 + #5
      strategyRef.current,
      requireMtfRef.current,
      ctrl.signal,
    ).then(signal => {
      if (ctrl.signal.aborted) return;
      setSignalMap(prev => {
        const next = new Map(prev);
        next.set(sym.yahoo, { symbol: sym, signal, loading: false, error: null });
        return next;
      });
    }).catch(e => {
      if (e.name === "AbortError") return;
      setSignalMap(prev => {
        const next = new Map(prev);
        next.set(sym.yahoo, { symbol: sym, signal: null, loading: false, error: e.message });
        return next;
      });
    });
  }, []); // stable

  // ── Fetch all ─────────────────────────────────────────────────────────────
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
    const prevKeys = prevItemsRef.current.map(i => i.sym).join(",");
    const nextKeys = items.map(i => i.sym).join(",");
    if (prevKeys === nextKeys) return;
    prevItemsRef.current = items;

    setSignalMap(prev => {
      const next = new Map();
      items.forEach(item => {
        if (prev.has(item.sym)) next.set(item.sym, prev.get(item.sym));
      });
      return next;
    });

    fetchAll(items);
  }, [items, fetchAll]);

  // FIX #4: single unified config change detector — covers interval too
  const prevConfigRef = useRef({ strategy, requireMtf, interval });
  useEffect(() => {
    const prev = prevConfigRef.current;
    if (
      prev.strategy   === strategy   &&
      prev.requireMtf === requireMtf &&
      prev.interval   === interval
    ) return;
    prevConfigRef.current = { strategy, requireMtf, interval };
    if (items.length) fetchAll(items);
  }, [strategy, requireMtf, interval, items, fetchAll]);

  // ── Auto-refresh timer ────────────────────────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => {
      if (items.length) fetchAll(items);
    }, REFRESH_INTERVAL_MS);
    return () => clearInterval(id);
  }, [items, fetchAll]);

  // ── Live WS signal → update matching card instantly ───────────────────────
  // FIX #3: filter by interval — don't mix signals from different timeframes
  useEffect(() => {
    if (!lastSignal) return;
    const sigYahoo    = lastSignal.symbol;
    const sigStrategy = lastSignal.strategy || "pro_mtf";
    const sigInterval = lastSignal.interval;

    if (!sigYahoo) return;
    if (sigStrategy !== strategy) return;
    // FIX #3: only accept signals matching the current interval
    if (sigInterval && sigInterval !== interval) return;

    setSignalMap(prev => {
      if (!prev.has(sigYahoo)) return prev;
      const cur  = prev.get(sigYahoo);
      const next = new Map(prev);
      next.set(sigYahoo, {
        ...cur,
        signal: {
          type:        lastSignal.signal_type || lastSignal.type,
          price:       lastSignal.price,
          sl:          lastSignal.sl,
          tp:          lastSignal.tp,
          rsi:         lastSignal.rsi,
          atr:         lastSignal.atr,
          confidence:  lastSignal.confidence,
          strategy:    lastSignal.strategy,
          time:        lastSignal.time,
          target_time: lastSignal.target_time,
          signal_id:   lastSignal.signal_id,
        },
        loading: false,
        error:   null,
      });
      return next;
    });

    setLiveYahoos(prev => new Set([...prev, sigYahoo]));
    clearTimeout(liveTimers.current[sigYahoo]);
    liveTimers.current[sigYahoo] = setTimeout(() => {
      setLiveYahoos(prev => {
        const next = new Set(prev);
        next.delete(sigYahoo);
        return next;
      });
    }, 10_000);
  }, [lastSignal, strategy, interval]);

  // ── Cleanup on unmount ────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      Object.values(abortRefs.current).forEach(c => c.abort());
      Object.values(liveTimers.current).forEach(clearTimeout);
    };
  }, []);

  // ── Sort: live first → BUY → SELL → no signal ────────────────────────────
  const entries = [...signalMap.values()].sort((a, b) => {
    const aLive = liveYahoos.has(a.symbol.yahoo) ? 1 : 0;
    const bLive = liveYahoos.has(b.symbol.yahoo) ? 1 : 0;
    if (aLive !== bLive) return bLive - aLive;

    const aHas = a.signal ? 1 : 0;
    const bHas = b.signal ? 1 : 0;
    if (aHas !== bHas) return bHas - aHas;

    if (a.signal && b.signal && a.signal.type !== b.signal.type) {
      return a.signal.type === "BUY" ? -1 : 1;
    }
    return 0;
  });

  const buyCount  = entries.filter(e => e.signal?.type === "BUY").length;
  const sellCount = entries.filter(e => e.signal?.type === "SELL").length;
  const liveCount = liveYahoos.size;

  return (
    <div className="radar-tab">
      {/* Summary bar */}
      <div className="radar-summary-bar">
        <span className="radar-stat">{entries.length} stocks</span>
        <span className="radar-stat buy">{buyCount} BUY</span>
        <span className="radar-stat sell">{sellCount} SELL</span>
        {liveCount > 0 && (
          <span className="radar-stat live">{liveCount} LIVE</span>
        )}
        {/* Active interval badge — makes it obvious what timeframe Radar is on */}
        <span className="radar-stat" style={{
          background: "rgba(41,121,255,.12)",
          color: "var(--blue)",
          border: "1px solid rgba(41,121,255,.2)",
        }}>
          {interval.toUpperCase()}
        </span>
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
            interval={interval}
          />
        ))}
      </div>
    </div>
  );
}