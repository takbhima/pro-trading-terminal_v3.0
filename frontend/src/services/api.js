/**
 * api.js — Single Responsibility: all HTTP calls to the backend.
 *
 * Added in v4:
 *  E4 — chartData now accepts requireMtf boolean → ?require_mtf=1
 *  E6 — validateSymbol() → GET /api/validate?sym=TICKER
 */

const BASE = "";

async function get(path) {
  const res = await fetch(BASE + path);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${path}`);
  return res.json();
}

async function post(path) {
  const res = await fetch(BASE + path, { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function del(path) {
  const res = await fetch(BASE + path, { method: "DELETE" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function patch(path) {
  const res = await fetch(BASE + path, { method: "PATCH" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export const api = {
  strategies:     ()                         => get("/api/strategies"),
  watchlist:      ()                         => get("/api/watchlist"),
  addWatchlist:   (sym, name)                => post(`/api/watchlist?sym=${encodeURIComponent(sym)}&name=${encodeURIComponent(name)}`),
  removeWatchlist:(sym)                      => del(`/api/watchlist/${encodeURIComponent(sym)}`),
  validateSymbol: (sym)                      => get(`/api/validate?sym=${encodeURIComponent(sym)}`),                    // E6
  chartData:      (sym, iv, strat, mtf)      => get(`/api/chartdata?symbol=${encodeURIComponent(sym)}&interval=${iv}&strategy=${strat}${mtf ? "&require_mtf=1" : ""}`),  // E4
  news:           (symbols)                  => get(`/api/news?symbols=${encodeURIComponent(symbols.join(","))}`),
  predict:        (sym, iv)                  => get(`/api/predict?symbol=${encodeURIComponent(sym)}&interval=${iv}`),
  getActiveTrade: (sym)                      => get(`/api/trade/${encodeURIComponent(sym)}`),
  closeTrade:     (sym, price)               => del(`/api/trade/${encodeURIComponent(sym)}?price=${price || 0}`),
  tradeHistory:   (sym)                      => get(`/api/trade/${encodeURIComponent(sym)}/history`),
  analytics:      ()                         => get("/api/trades/analytics"),                                            // E2
  settings:       ()                         => get("/api/settings"),
  setCooldown:    (bars)                     => patch(`/api/settings/cooldown?bars=${bars}`),                           // E3
  setMtf:         (enabled)                  => patch(`/api/settings/mtf?enabled=${enabled}`),                         // E4
};
