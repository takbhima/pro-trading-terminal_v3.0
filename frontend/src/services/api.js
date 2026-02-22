/**
 * api.js — Single Responsibility: all HTTP calls to the backend.
 * Components never call fetch() directly — they use these functions.
 * Mirrors the DIP: components depend on this abstraction, not on fetch().
 */

const BASE = "";  // same origin

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

export const api = {
  strategies:    ()                    => get("/api/strategies"),
  watchlist:     ()                    => get("/api/watchlist"),
  addWatchlist:  (sym, name)           => post(`/api/watchlist?sym=${encodeURIComponent(sym)}&name=${encodeURIComponent(name)}`),
  removeWatchlist:(sym)                => del(`/api/watchlist/${encodeURIComponent(sym)}`),
  chartData:     (sym, iv, strat)      => get(`/api/chartdata?symbol=${encodeURIComponent(sym)}&interval=${iv}&strategy=${strat}`),
  news:          (symbols)             => get(`/api/news?symbols=${encodeURIComponent(symbols.join(","))}`),
  predict:       (sym, iv)             => get(`/api/predict?symbol=${encodeURIComponent(sym)}&interval=${iv}`),
  getActiveTrade:(sym)                 => get(`/api/trade/${encodeURIComponent(sym)}`),
  closeTrade:    (sym, price)          => del(`/api/trade/${encodeURIComponent(sym)}?price=${price || 0}`),
  tradeHistory:  (sym)                 => get(`/api/trade/${encodeURIComponent(sym)}/history`),
};
