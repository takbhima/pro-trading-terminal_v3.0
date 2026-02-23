/**
 * ChartPanel.jsx — jumpToSignal integration
 * ─────────────────────────────────────────────────────────────────────────
 * App.jsx now passes a `jumpToSignal` prop to ChartPanel:
 *   { time: <unix_timestamp>, signal_id: "<sym>_<time>", _at: <Date.now()> }
 *
 * Add the following useEffect to your existing ChartPanel component.
 * The `_at` field ensures the effect fires even if the user clicks the
 * same signal card twice.
 *
 * REQUIRED: chartRef must be your LightweightCharts IChartApi reference.
 * ─────────────────────────────────────────────────────────────────────────
 */

// ── Add this prop to your ChartPanel function signature: ──────────────────
//
//   export default function ChartPanel({ symbol, interval, strategy,
//                                        requireMtf, fetchKey, jumpToSignal }) {

// ── Add this useEffect inside ChartPanel (after chartRef is initialised): ─

useEffect(() => {
  if (!jumpToSignal || !chartRef.current) return;

  const { time } = jumpToSignal;
  if (!time) return;

  try {
    const ts = chartRef.current.timeScale();

    // Window width in seconds around the signal:
    // Show ±20 bars of context based on interval
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
    const barSecs  = INTERVAL_SECONDS[interval] || 300;
    const halfWin  = barSecs * 20;  // 20 bars either side

    ts.setVisibleRange({
      from: time - halfWin,
      to:   time + halfWin,
    });
  } catch (err) {
    // setVisibleRange can throw if range is outside chart data — ignore silently
    console.warn("[ChartPanel] jumpToSignal scroll failed:", err.message);
  }
}, [jumpToSignal, interval]);  // interval changes the window size

// ── That's all. No other changes needed to ChartPanel. ───────────────────
