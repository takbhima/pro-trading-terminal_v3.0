/**
 * useChartData — fetches OHLCV + signals for a symbol/interval/strategy.
 * E4: Accepts requireMtf flag → passes require_mtf=1 to API when enabled.
 *
 * Fix: AbortController signal is now forwarded to the underlying fetch call
 * so in-flight requests are truly cancelled on re-render, preventing stale
 * state updates from out-of-order responses.
 */
import { useState, useEffect, useRef } from "react";

export function useChartData(symbol, interval, strategy, requireMtf = false, fetchKey = 0) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const abortRef = useRef(null);

  useEffect(() => {
    if (!symbol) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    // Reset data to null immediately so consumers don't see stale data
    // from the previous symbol/interval/strategy while the new fetch is in flight.
    setData(null);
    setLoading(true);
    setError(null);

    const url = `/api/chartdata?symbol=${encodeURIComponent(symbol)}&interval=${interval}&strategy=${strategy}${requireMtf ? "&require_mtf=1" : ""}`;

    fetch(url, { signal: ctrl.signal })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((d) => {
        setData(d);
        setError(d.error || null);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      })
      .finally(() => {
        if (!ctrl.signal.aborted) setLoading(false);
      });

    return () => ctrl.abort();
  // fetchKey is intentionally included — it forces a fresh fetch whenever
  // the parent increments it (strategy switch, interval switch, MTF toggle, symbol scan).
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbol, interval, strategy, requireMtf, fetchKey]);

  return { data, loading, error };
}
