/**
 * utils.js — Pure utility functions.
 * No side effects, no I/O — mirrors TargetTimeEstimator's philosophy.
 */

/** Format price with appropriate decimal places */
export function fmt(p) {
  if (p == null) return "—";
  const n = Number(p);
  if (isNaN(n)) return "—";
  return n >= 1000 ? n.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : n.toFixed(2);
}

/** Timezone offset for LightweightCharts (browser local time) */
export const TZ_OFFSET_S = new Date().getTimezoneOffset() * -60;

export function applyTZ(ts) {
  return typeof ts === "number" ? ts + TZ_OFFSET_S : ts;
}

export function applyTZtoSeries(arr) {
  return arr.map((item) => ({ ...item, time: applyTZ(item.time) }));
}

/** Human readable elapsed minutes */
export function elapsedMins(isoString) {
  return Math.max(0, Math.round((Date.now() - new Date(isoString).getTime()) / 60000));
}

/** Signal rationale per strategy — pure lookup */
export const SIGNAL_WHY = {
  pro_mtf: (s) =>
    s.type === "BUY"
      ? ["EMA 9 crossed above EMA 21", `RSI ${s.rsi} > 50 — bullish`, "Price above EMA 200", "Supertrend bullish"]
      : ["EMA 9 crossed below EMA 21", `RSI ${s.rsi} < 50 — bearish`, "Price below EMA 200", "Supertrend bearish"],
  vwap_ema: (s) =>
    s.type === "BUY"
      ? ["Price crossed above VWAP", "EMA 9 > EMA 21", `RSI ${s.rsi} > 50`]
      : ["Price crossed below VWAP", "EMA 9 < EMA 21", `RSI ${s.rsi} < 50`],
  rsi_reversal: (s) =>
    s.type === "BUY"
      ? [`RSI ${s.rsi} crossed above 30 — oversold exit`, "Price above EMA 50"]
      : [`RSI ${s.rsi} crossed below 70 — overbought exit`, "Price below EMA 50"],
  bollinger: (s) =>
    s.type === "BUY"
      ? ["Price broke above upper Bollinger Band", `RSI ${s.rsi} > 55`, "Volume confirmed"]
      : ["Price broke below lower Bollinger Band", `RSI ${s.rsi} < 45`, "Volume confirmed"],
  macd: (s) =>
    s.type === "BUY"
      ? ["MACD crossed above Signal", "Histogram positive", `RSI ${s.rsi} > 50`]
      : ["MACD crossed below Signal", "Histogram negative", `RSI ${s.rsi} < 50`],
  supertrend_scalper: (s) =>
    s.type === "BUY"
      ? [`Fast Supertrend(2,7) flipped bullish`, `RSI ${s.rsi} > 45`]
      : [`Fast Supertrend(2,7) flipped bearish`, `RSI ${s.rsi} < 55`],
};

export function getWhyReasons(strategy, signal) {
  const fn = SIGNAL_WHY[strategy] || SIGNAL_WHY["pro_mtf"];
  return fn(signal);
}

/** Classify exit reason for badge styling */
export function exitReasonClass(reason) {
  if (!reason) return "manual";
  const r = reason.toLowerCase();
  if (r.includes("target")) return "target";
  if (r.includes("stop"))   return "stop";
  if (r.includes("time"))   return "time";
  if (r.includes("eod"))    return "eod";
  return "manual";
}
