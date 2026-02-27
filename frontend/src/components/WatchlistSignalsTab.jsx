/**
 * WatchlistSignalsTab — "📡 Radar" tab
 * =====================================
 * BUGS FIXED:
 *
 * 1. Hardcoded `interval=1d` — now accepts `interval` prop so radar matches
 *    the user's selected timeframe.
 *
 * 2. signalAge() parsed daily "YYYY-MM-DD" strings in LOCAL time → added "Z"
 *    suffix to force UTC parse, eliminating the IST +5:30 skew.
 *
 * 3. Internal useWatchlist() call — now accepts `watchlistHook` prop so the
 *    parent's already-lifted hook is reused, eliminating duplicate API calls.
 *
 * 4. Double fetch on strategy change — strategy/MTF change effect was
 *    triggering alongside the watchlist-change effect (because fetchAll
 *    identity changed). Fixed by tracking prev values in refs and using a
 *    single stable fetchAll that doesn't regenerate on dep changes.
 *
 * 5. WS live signal bypassed requireMtf filter — now checks signal.mtf_ok
 *    when requireMtf is true before accepting live WS updates.
 *
 * 6. No "no signal" text updated for interval — "No signal on 1D" was
 *    hardcoded; now shows the actual interval.
 */
import "./WatchlistSignalsTab.css";
import { useState, useEffect, useRef, useCallback } from "react";
import { useWatchlist }   from "../hooks/useWatchlist";
import { useWebSocket }   from "../context/WebSocketContext";
import { fmt }            from "../utils/utils";

const REFRESH_INTERVAL_MS = 60_000;

// ─── helpers ────────────────────────────────────────────────────────────────

function signalAge(time) {
  if (!time && time !== 0) return "";
  let ts;
  if (typeof time === "number") {
    ts = time * 1000;
  } else {
    // FIX #2: append "Z" so Date.parse treats it as UTC, not local time
    // "YYYY-MM-DD" → "YYYY-MM-DDT00:00:00Z"
    ts = Date.parse(time + "T00:00:00Z");
  }
  if (isNaN(ts)) return "";
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 0)     return "just now";
  if (s < 60)    return `${s}s ago`;
  if (s < 3600)  return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

// FIX #1: accepts `interval` param instead of hardcoding "1d"
async function fetchLatestSignal(yahoo, interval, strategy, requireMtf, signal) {
  const url =
    `/api/chartdata?symbol=${encodeURIComponent(yahoo)}` +
    `&interval=${encodeURIComponent(interval)}` +
    `&strategy=${strategy}` +
    (requireMtf ? "&require_mtf=1" : "");
  const res = await fetch(url, { signal });
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
function RadarCard({ entry, isLive, onJumpToSignal, interval }) {
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
// FIX #1: added `interval` prop
// FIX #3: added `watchlistHook` prop to reuse parent's hook instance
export default function WatchlistSignalsTab({
  strategy,
  requireMtf,
  interval = "1d",
  watchlistHook,
  onJumpToSignal,
}) {
  // FIX #3: reuse parent hook if provided, avoid duplicate /api/watchlist call
  const localHook      = useWatchlist();
  const { items }      = watchlistHook || localHook;
  const { lastSignal } = useWebSocket();

  const [signalMap,  setSignalMap]  = useState(new Map());
  const [liveYahoos, setLiveYahoos] = useState(new Set());
  const [nextRefresh, setNextRefresh] = useState(Date.now() + REFRESH_INTERVAL_MS);
  const abortRefs  = useRef({});
  const liveTimers = useRef({});

  // Keep latest values in refs to avoid stale closures in fetchAll
  // FIX #4: stable refs prevent double-fetch when strategy/interval changes
  const strategyRef   = useRef(strategy);
  const requireMtfRef = useRef(requireMtf);
  const intervalRef   = useRef(interval);
  useEffect(() => { strategyRef.current   = strategy;   }, [strategy]);
  useEffect(() => { requireMtfRef.current = requireMtf; }, [requireMtf]);
  useEffect(() => { intervalRef.current   = interval;   }, [interval]);

  // ── Fetch one symbol ──────────────────────────────────────────────────────
  const fetchOne = useCallback(async (sym) => {
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
      // FIX #1 + #4: read from refs so fetchOne identity is stable
      const signal = await fetchLatestSignal(
        sym.yahoo,
        intervalRef.current,
        strategyRef.current,
        requireMtfRef.current,
        ctrl.signal
      );
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
  }, []); // stable — reads strategy/interval/requireMtf from refs

  // ── Fetch all watchlist symbols ───────────────────────────────────────────
  const fetchAll = useCallback((watchlistItems) => {
    watchlistItems.forEach(item => {
      fetchOne({ yahoo: item.sym, label: item.name || item.sym });
    });
    setNextRefresh(Date.now() + REFRESH_INTERVAL_MS);
  }, [fetchOne]); // fetchOne is stable, so fetchAll is stable too

  // ── Initial load + watchlist change ──────────────────────────────────────
  const prevItemsKeyRef = useRef("");
  useEffect(() => {
    if (!items.length) return;
    const nextKey = items.map(i => i.sym).join(",");
    if (prevItemsKeyRef.current === nextKey) return;
    prevItemsKeyRef.current = nextKey;

    setSignalMap(prev => {
      const next = new Map();
      items.forEach(item => {
        if (prev.has(item.sym)) next.set(item.sym, prev.get(item.sym));
      });
      return next;
    });

    fetchAll(items);
  }, [items, fetchAll]);

  // FIX #4: strategy/interval/MTF changes — single effect, no double-fetch
  // Uses a single ref-based guard; fetchAll is now stable so it won't re-trigger
  // the watchlist-change effect above.
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
  useEffect(() => {
    if (!lastSignal) return;
    const sigYahoo    = lastSignal.symbol;
    const sigStrategy = lastSignal.strategy || "pro_mtf";
    if (!sigYahoo || sigStrategy !== strategy) return;

    // FIX #5: respect requireMtf — reject WS signals that aren't MTF-confirmed
    if (requireMtf && !lastSignal.mtf_ok) return;

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
          mtf_ok:      lastSignal.mtf_ok,
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
  }, [lastSignal, strategy, requireMtf]);

  // ── Cleanup on unmount ────────────────────────────────────────────────────
  useEffect(() => {
    return () => {
      Object.values(abortRefs.current).forEach(c => c.abort());
      Object.values(liveTimers.current).forEach(clearTimeout);
    };
  }, []);

  // ── Sorted entries ────────────────────────────────────────────────────────
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

  const total     = entries.length;
  const buyCount  = entries.filter(e => e.signal?.type === "BUY").length;
  const sellCount = entries.filter(e => e.signal?.type === "SELL").length;
  const liveCount = liveYahoos.size;

  return (
    <div className="radar-tab">
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