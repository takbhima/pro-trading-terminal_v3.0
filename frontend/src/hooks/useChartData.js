/**
 * useChartData — fetches OHLCV + signals for a symbol/interval/strategy.
 * Returns loading state, data, and error.
 */
import { useState, useEffect, useRef } from "react";
import { api } from "../services/api";

export function useChartData(symbol, interval, strategy) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const abortRef = useRef(null);

  useEffect(() => {
    if (!symbol) return;
    abortRef.current?.abort();
    const ctrl = new AbortController();
    abortRef.current = ctrl;

    setLoading(true);
    setError(null);

    api.chartData(symbol, interval, strategy)
      .then((d) => {
        if (!ctrl.signal.aborted) {
          setData(d);
          setError(d.error || null);
        }
      })
      .catch((e) => { if (!ctrl.signal.aborted) setError(e.message); })
      .finally(() => { if (!ctrl.signal.aborted) setLoading(false); });

    return () => ctrl.abort();
  }, [symbol, interval, strategy]);

  return { data, loading, error };
}
