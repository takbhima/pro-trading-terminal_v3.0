/**
 * ChartPanel — E4: Accepts requireMtf prop and passes to useChartData.
 * Shows MTF filter indicator in toolbar when active.
 * NEW: jumpToSignal prop scrolls the chart to a specific signal timestamp.
 *
 * BUG FIX: jumpToSignal now handles both intraday (unix integer) and daily
 * (YYYY-MM-DD string) signal timestamps. Previously, string timestamps
 * caused NaN in arithmetic which silently failed.
 */
import { useEffect, useRef } from "react";
import { useChartData }      from "../hooks/useChartData";
import { useWebSocket }      from "../context/WebSocketContext";
import { applyTZ, applyTZtoSeries, fmt } from "../utils/utils";

// Seconds per bar for each interval (used to compute visible window around a signal)
const INTERVAL_SECONDS = {
  "1m":  60,
  "3m":  180,
  "5m":  300,
  "15m": 900,
  "30m": 1800,
  "1h":  3600,
  "60m": 3600,
  "1d":  86400,
  "1wk": 604800,
};

/**
 * Normalise a signal time value to a unix timestamp (seconds).
 * Intraday signals come as integers (unix epoch).
 * Daily/weekly signals come as "YYYY-MM-DD" strings.
 */
function normaliseSignalTime(time) {
  if (typeof time === "number") return time;
  if (typeof time === "string") {
    // Parse ISO date string — treat as UTC midnight
    const ms = Date.parse(time + "T00:00:00Z");
    return isNaN(ms) ? null : Math.floor(ms / 1000);
  }
  return null;
}

export default function ChartPanel({ symbol, interval, strategy, requireMtf, fetchKey = 0, jumpToSignal }) {
  const containerRef = useRef(null);
  const chartRef     = useRef(null);
  const seriesRef    = useRef({ candle: null, ema9: null, ema21: null, ema200: null });
  const { data, loading, error } = useChartData(symbol.yahoo, interval, strategy, requireMtf, fetchKey);
  const { lastTick } = useWebSocket();

  // ── Init chart once ──────────────────────────────────────────────────────
  useEffect(() => {
    const el = containerRef.current;
    if (!el || !window.LightweightCharts) return;

    const chart = window.LightweightCharts.createChart(el, {
      layout:          { background: { color: "#080f1a" }, textColor: "#6b8cae" },
      grid:            { vertLines: { color: "#0d1a2d" }, horzLines: { color: "#0d1a2d" } },
      crosshair:       { mode: window.LightweightCharts.CrosshairMode.Normal },
      rightPriceScale: { borderColor: "#1a2d48" },
      timeScale:       { borderColor: "#1a2d48", timeVisible: true, secondsVisible: false },
      width:  el.offsetWidth,
      height: el.offsetHeight,
    });

    const candle = chart.addCandlestickSeries({
      upColor: "#00e676", downColor: "#ff3d57",
      borderUpColor: "#00e676", borderDownColor: "#ff3d57",
      wickUpColor: "#00e676", wickDownColor: "#ff3d57",
    });
    const ema9   = chart.addLineSeries({ color: "#00e676", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const ema21  = chart.addLineSeries({ color: "#ff3d57", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const ema200 = chart.addLineSeries({ color: "#2979ff", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });

    chartRef.current  = chart;
    seriesRef.current = { candle, ema9, ema21, ema200 };

    const ro = new ResizeObserver(() => chart.resize(el.offsetWidth, el.offsetHeight));
    ro.observe(el);
    return () => { ro.disconnect(); chart.remove(); };
  }, []);

  // ── Load chart data ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!data || !seriesRef.current.candle) return;
    const { candle, ema9, ema21, ema200 } = seriesRef.current;

    try { candle.setData(applyTZtoSeries(data.candles || [])); } catch {}
    try { ema9.setData(applyTZtoSeries(data.ema9 || [])); }     catch {}
    try { ema21.setData(applyTZtoSeries(data.ema21 || [])); }   catch {}
    try { ema200.setData(applyTZtoSeries(data.ema200 || [])); } catch {}

    if (data.signals?.length) {
      try {
        candle.setMarkers(
          data.signals
            .filter((s) => s.time != null)
            .map((s) => ({
              time:     applyTZ(s.time),
              position: s.type === "BUY" ? "belowBar" : "aboveBar",
              color:    s.type === "BUY" ? "#00e676"  : "#ff3d57",
              shape:    s.type === "BUY" ? "arrowUp"  : "arrowDown",
              text:     s.type,
              size:     2,
            }))
        );
      } catch {}
    } else {
      try { candle.setMarkers([]); } catch {}
    }

    chartRef.current?.timeScale().fitContent();
  }, [data]);

  // ── Live candle update ───────────────────────────────────────────────────
  useEffect(() => {
    if (!lastTick?.bar || lastTick.symbol !== symbol.yahoo || !seriesRef.current.candle) return;
    try {
      seriesRef.current.candle.update({
        time:  applyTZ(lastTick.bar.time),
        open:  lastTick.bar.open,
        high:  lastTick.bar.high,
        low:   lastTick.bar.low,
        close: lastTick.bar.close,
      });
    } catch {}
  }, [lastTick, symbol.yahoo]);

  // ── Jump to signal (when user clicks a signal history card) ──────────────
  useEffect(() => {
    if (!jumpToSignal || !chartRef.current) return;

    const { time } = jumpToSignal;
    if (time == null) return;

    try {
      const ts = chartRef.current.timeScale();

      // FIX: normalise to unix seconds first — handles both string (daily)
      // and number (intraday) signal timestamps.
      const unixTime = normaliseSignalTime(time);
      if (!unixTime) return;

      // Apply the same TZ offset used for chart rendering
      const adjustedTime = applyTZ(unixTime);

      // Show ±20 bars of context around the clicked signal
      const barSecs = INTERVAL_SECONDS[interval] || 300;
      const halfWin = barSecs * 20;

      ts.setVisibleRange({
        from: adjustedTime - halfWin,
        to:   adjustedTime + halfWin,
      });
    } catch (err) {
      // setVisibleRange can throw if range is outside chart data — silently ignore
      console.warn("[ChartPanel] jumpToSignal scroll failed:", err?.message);
    }
  // _at in jumpToSignal ensures the effect fires even when clicking the same card twice
  }, [jumpToSignal, interval]); // eslint-disable-line react-hooks/exhaustive-deps

  const lastClose = data?.candles?.at(-1)?.close;
  const sigCount  = data?.signals?.length || 0;
  const mtfActive = data?.mtf_active;

  return (
    <div className="chart-wrap">
      <div className="chart-toolbar" title="All times shown in local timezone">
        <span className="ct-sym">{symbol.label}</span>
        {lastClose && <span className="ct-px">{fmt(lastClose)}</span>}
        <span className="tz-badge">LOCAL</span>
        {mtfActive && (
          <span className="mtf-active-badge" title="Multi-timeframe confirmation filter is ON">
            🔒 MTF
          </span>
        )}
        <div className="ema-legend">
          <span className="ema-li"><span className="ema-dot" style={{ background: "#00e676" }} />EMA9</span>
          <span className="ema-li"><span className="ema-dot" style={{ background: "#ff3d57" }} />EMA21</span>
          <span className="ema-li"><span className="ema-dot" style={{ background: "#2979ff", height: 3 }} />EMA200</span>
        </div>
        {sigCount > 0 && <span className="ct-sigs">{sigCount} signals</span>}
        {sigCount === 0 && !loading && (
          <span className="ct-sigs" style={{ color: "var(--dim)" }}>
            {mtfActive ? "No signals (MTF filtered)" : "No signals on this TF"}
          </span>
        )}
      </div>

      <div className="chart-container" ref={containerRef} />

      {loading && (
        <div className="chart-loader">
          <div className="spinner" />
          <span>Loading…</span>
        </div>
      )}
      {error && !loading && (
        <div className="chart-loader">
          <span style={{ color: "var(--red)" }}>⚠ {error}</span>
        </div>
      )}
    </div>
  );
}