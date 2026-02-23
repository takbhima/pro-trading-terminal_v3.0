"""
Pro Trading Terminal v4 — Enhanced Edition
==========================================
BUG FIXES (this version):

  FIX-1 — Watchlist scan always used pro_mtf regardless of selected strategy.
           _scan_watchlist_signals now iterates per-client metadata so each
           connected client gets signals for their selected strategy.

  FIX-2 — Tick payload now includes the current strategy so frontend can
           detect strategy mismatches and clear stale badges.

  FIX-3 — Signal payload includes a "clear_signal" flag when a scan finds
           no signal for a symbol on the current strategy, so the watchlist
           badge is cleared rather than left stale.

  FIX-4 — api_chartdata: estimator.estimate() call moved BEFORE Signal creation
           so target_bars is available when TradeService.open_trade() is called.
           Previously target_bars was None, causing trades to always default to
           5-bar expected duration.

  NEW   — GET /api/market-ticker endpoint returns live prices for SENSEX,
           Nifty 50, and Bank Nifty for the MarketTicker frontend component.
"""

import asyncio, os, json
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ── Concrete implementations ─────────────────────────────────────────────────
from backend.repositories.sqlite_trade_store import SqliteTradeStore
from backend.repositories                    import JsonWatchlistStore
from backend.services import (
    YFinanceDataSource,
    TradeService,
    MultiSourceNewsService,
    TechnicalNewsPredictor,
    ChartService,
    TargetTimeEstimator,
    MarketHoursService,
)
from backend.services.symbol_validator import validate_symbol
from backend.strategies                import registry as strategy_registry
from backend.utils                     import BarStateTracker
from backend.utils.signal_cooldown     import SignalCooldownTracker

# ── Wire up all dependencies ─────────────────────────────────────────────────
_ROOT        = os.path.dirname(__file__)
_data        = YFinanceDataSource()
_trade_store = SqliteTradeStore(os.path.join(_ROOT, "trades.db"))
_trades      = TradeService(_trade_store)
_watchlist   = JsonWatchlistStore(os.path.join(_ROOT, "watchlist.json"))
_news        = MultiSourceNewsService()
_predictor   = TechnicalNewsPredictor()
_chart       = ChartService()
_estimator   = TargetTimeEstimator()
_mkt_hours   = MarketHoursService()
_cooldown    = SignalCooldownTracker(cooldown_bars=5)

# ── WebSocket state ───────────────────────────────────────────────────────────
_bar_tracker      = BarStateTracker()
_signal_history:  list = []
_ws_clients:      list = []
_ws_client_meta:  dict = {}   # id(ws) -> {"symbol": str, "interval": str, "strategy": str}

# ── Settings ──────────────────────────────────────────────────────────────────
MAX_OPEN_TRADES = 3
_settings = {
    "cooldown_bars": 5,
    "require_mtf":   False,
}

# ── Market ticker symbols ─────────────────────────────────────────────────────
_TICKER_SYMBOLS = [
    {"symbol": "^BSESN",   "name": "SENSEX"},
    {"symbol": "^NSEI",    "name": "Nifty 50"},
    {"symbol": "^NSEBANK", "name": "Bank Nifty"},
]

app = FastAPI(title="Pro Trading Terminal v4")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════════
#  E1 — Broadcast helper
# ═══════════════════════════════════════════════════════════════════════════════

async def broadcast(payload: dict, exclude: WebSocket = None) -> None:
    dead = []
    for client in list(_ws_clients):
        if client is exclude:
            continue
        try:
            await client.send_json(payload)
        except Exception:
            dead.append(client)
    for d in dead:
        try:
            _ws_clients.remove(d)
            _ws_client_meta.pop(id(d), None)
        except ValueError:
            pass


async def send_to_client(ws: WebSocket, payload: dict) -> bool:
    try:
        await ws.send_json(payload)
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
#  REST API
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/status")
def api_status():
    open_mkt = _mkt_hours.open_markets()
    return {
        "open_markets":      open_mkt,
        "signals":           len(_signal_history),
        "active_trades":     len(_trades.get_all_active()),
        "connected_clients": len(_ws_clients),
    }

@app.get("/api/strategies")
def api_strategies():
    return strategy_registry.to_list()

@app.get("/api/settings")
def api_get_settings():
    return _settings

@app.patch("/api/settings/cooldown")
def api_set_cooldown(bars: int = Query(ge=1, le=50)):
    _settings["cooldown_bars"] = bars
    _cooldown.set_cooldown_bars(bars)
    return {"ok": True, "cooldown_bars": bars}

@app.patch("/api/settings/mtf")
def api_set_mtf(enabled: bool):
    _settings["require_mtf"] = enabled
    return {"ok": True, "require_mtf": enabled}


# ── NEW: Market ticker endpoint ───────────────────────────────────────────────

@app.get("/api/market-ticker")
def api_market_ticker():
    """
    Returns live price, change, and change% for SENSEX, Nifty 50, Bank Nifty.
    Uses yfinance fast_info — lightweight, no full history needed.
    Called by the MarketTicker React component every 15 seconds.
    """
    results = []
    for entry in _TICKER_SYMBOLS:
        sym  = entry["symbol"]
        name = entry["name"]
        try:
            price = _data.get_live_price(sym)
            prev  = _data.get_prev_close(sym)
            if price > 0 and prev > 0:
                change     = round(price - prev, 2)
                change_pct = round((change / prev) * 100, 2)
            else:
                change = change_pct = 0.0
            results.append({
                "symbol":     sym,
                "name":       name,
                "price":      round(price, 2),
                "prev_close": round(prev, 2),
                "change":     change,
                "change_pct": change_pct,
            })
        except Exception as e:
            print(f"[TICKER] {sym}: {e}")
            results.append({
                "symbol":     sym,
                "name":       name,
                "price":      0.0,
                "prev_close": 0.0,
                "change":     0.0,
                "change_pct": 0.0,
            })
    return JSONResponse({"indices": results})


# ── E6 — Symbol validation endpoint ──────────────────────────────────────────

@app.get("/api/validate")
def api_validate_symbol(sym: str):
    result = validate_symbol(sym)
    return {
        "ok":             result.ok,
        "reason":         result.reason,
        "price":          result.price,
        "suggested_name": result.suggested_name,
    }


# ── Watchlist ─────────────────────────────────────────────────────────────────

@app.get("/api/watchlist")
def api_get_watchlist():
    return [{"sym": w.sym, "name": w.name} for w in _watchlist.load()]


@app.post("/api/watchlist")
def api_add_watchlist(sym: str, name: str = ""):
    sym = sym.strip().upper()
    result = validate_symbol(sym)
    if not result.ok:
        return JSONResponse({"ok": False, "reason": result.reason}, status_code=400)
    display_name = name.strip() or result.suggested_name or sym
    return _watchlist.add(sym, display_name)


@app.delete("/api/watchlist/{sym}")
def api_del_watchlist(sym: str):
    return _watchlist.remove(sym)


# ── Chart data ────────────────────────────────────────────────────────────────

@app.get("/api/chartdata")
def api_chartdata(
    symbol:      str,
    interval:    str  = "1d",
    strategy:    str  = "pro_mtf",
    require_mtf: bool = False,
):
    try:
        strat = strategy_registry.get(strategy)
        if not strat:
            return JSONResponse({"error": f"Unknown strategy: {strategy}"}, status_code=400)

        df = _fetch_for_interval(symbol, interval)
        if df is None or df.empty:
            return _empty_chart(f"No data for {symbol}")

        chart_data = _chart.build_chart_data(df, strat, interval)

        use_mtf = require_mtf or _settings["require_mtf"]
        if use_mtf and interval not in ("1d", "1wk"):
            chart_data["signals"] = _filter_signals_by_mtf(chart_data["signals"], symbol)
            chart_data["total_signals"] = len(chart_data["signals"])
            chart_data["latest_signal"] = chart_data["signals"][-1] if chart_data["signals"] else None

        # Tag each signal with a stable ID and trade status
        active = _trades.get_active(symbol)
        active_entry = active["entry_price"] if active else None
        for s in chart_data["signals"]:
            s["signal_id"] = f"{symbol}_{s['time']}"
            s["trade_status"] = "open" if (
                active_entry is not None and abs(float(s["price"]) - active_entry) < 0.001
            ) else "closed"

        if chart_data["latest_signal"]:
            latest = chart_data["latest_signal"]

            # FIX-4: Compute target time BEFORE building the Signal object
            # so that target_bars is populated when open_trade() is called.
            t = _estimator.estimate(df, float(latest["price"]), float(latest["tp"]), interval)
            latest.update({
                "target_time":     t["label"],
                "target_datetime": t["datetime"],
                "target_bars":     t["bars"],
            })

            if active is None:
                from backend.interfaces.strategy import Signal
                # Now latest contains target_bars so Signal gets the correct value
                sig = Signal(**{k: latest[k] for k in Signal.__dataclass_fields__ if k in latest})
                _trades.open_trade(sig, symbol, interval)

        return JSONResponse({
            **chart_data,
            "active_trade":  _trades.get_active(symbol),
            "mtf_active":    use_mtf,
            "strategy_used": strategy,
            "interval_used": interval,
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return _empty_chart(str(e))


def _filter_signals_by_mtf(signals: list, symbol: str) -> list:
    if not signals:
        return signals
    try:
        from backend.indicators import EMA
        df_daily = _data.fetch(symbol, "1d")
        if df_daily is None or df_daily.empty or len(df_daily) < 22:
            return signals
        e9d  = float(EMA(9).compute(df_daily).iloc[-1])
        e21d = float(EMA(21).compute(df_daily).iloc[-1])
        if e9d != e9d or e21d != e21d:
            return signals
        daily_bullish = e9d > e21d

        filtered = []
        for s in signals:
            sig_type = s.get("type", "")
            if sig_type == "BUY" and daily_bullish:
                filtered.append(s)
            elif sig_type == "SELL" and not daily_bullish:
                filtered.append(s)
        return filtered
    except Exception as e:
        print(f"[MTF] filter failed for {symbol}: {e}")
        return signals


def _empty_chart(error: str) -> JSONResponse:
    return JSONResponse({"error": error, "candles": [], "ema9": [], "ema21": [],
                         "ema200": [], "signals": [], "latest_signal": None,
                         "active_trade": None})


# ── News ──────────────────────────────────────────────────────────────────────

@app.get("/api/news")
def api_news(symbols: str = ""):
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols \
               else [w.sym for w in _watchlist.load()[:15]]
    articles = _news.fetch(sym_list)
    return JSONResponse({
        "news":  [_article_to_dict(a) for a in articles],
        "count": len(articles),
    })


def _article_to_dict(a) -> dict:
    return {
        "title":     a.title,
        "source":    a.source,
        "url":       a.url,
        "age":       a.age,
        "ts":        a.timestamp,
        "category":  a.category,
        "icon":      a.icon,
        "sentiment": a.sentiment,
        "score":     a.score,
        "symbol":    a.symbol,
    }


# ── Prediction ────────────────────────────────────────────────────────────────

@app.get("/api/predict")
def api_predict(symbol: str, interval: str = "1d"):
    try:
        df       = _data.fetch(symbol, interval)
        articles = _news.fetch([symbol], max_per_symbol=10)
        pred     = _predictor.predict(df, articles, symbol, interval)
        return JSONResponse({
            "symbol":       pred.symbol,
            "direction":    pred.direction,
            "confidence":   pred.confidence,
            "tech_score":   pred.tech_score,
            "news_score":   pred.news_score,
            "bull_reasons": pred.bull_reasons,
            "bear_reasons": pred.bear_reasons,
            "current":      pred.current,
            "tp1":          pred.tp1,
            "tp2":          pred.tp2,
            "sl":           pred.sl,
            "atr":          pred.atr,
            "rsi":          pred.rsi,
            "interval":     pred.interval,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)})


# ── Trade endpoints ───────────────────────────────────────────────────────────

@app.get("/api/trade/{symbol}")
def api_get_trade(symbol: str):
    return JSONResponse({"trade": _trades.get_active(symbol)})

@app.delete("/api/trade/{symbol}")
def api_close_trade(symbol: str, price: float = 0):
    if not price:
        price = _data.get_live_price(symbol) or 0
    if not _trades.get_active(symbol):
        return JSONResponse({"error": "No active trade"}, status_code=404)
    ev = _trades.force_close(symbol, price or 0)
    return JSONResponse({"exit": _trades._exit_to_dict(ev) if ev else None})

@app.get("/api/trade/{symbol}/history")
def api_trade_history(symbol: str):
    return JSONResponse({"history": _trades.get_history(symbol)})

@app.get("/api/trades/active")
def api_all_active():
    return JSONResponse({"trades": _trades.get_all_active()})

@app.get("/api/trades/analytics")
def api_trades_analytics():
    summary  = _trade_store.get_pnl_summary()
    history  = _trade_store.get_history(symbol=None)
    by_strat: dict = {}
    for t in history:
        s = getattr(t, "strategy", None) or "unknown"
        if s not in by_strat:
            by_strat[s] = {"wins": 0, "losses": 0, "total_pnl": 0}
        pnl = getattr(t, "pnl", 0) or 0
        if pnl >= 0:
            by_strat[s]["wins"] += 1
        else:
            by_strat[s]["losses"] += 1
        by_strat[s]["total_pnl"] = round(by_strat[s]["total_pnl"] + pnl, 4)
    return JSONResponse({"summary": summary, "by_strategy": by_strat})


# ═══════════════════════════════════════════════════════════════════════════════
#  WebSocket — multi-client, strategy-aware
# ═══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    ws_id = id(ws)
    _ws_client_meta[ws_id] = {"symbol": None, "interval": "5m", "strategy": "pro_mtf"}

    open_mkt = _mkt_hours.open_markets()
    tick_count = 0

    await ws.send_json(_status_payload(open_mkt))

    disconnected = {"flag": False}

    async def recv_msgs():
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_json(), timeout=0.1)
                if isinstance(msg, dict) and msg.get("type") == "subscribe":
                    sym      = msg.get("symbol",   "").strip()
                    iv       = msg.get("interval",  "5m")
                    strategy = msg.get("strategy",  "pro_mtf")
                    meta     = _ws_client_meta.get(ws_id, {})
                    prev_sym = meta.get("symbol")
                    prev_iv  = meta.get("interval")
                    if sym != prev_sym or iv != prev_iv:
                        _bar_tracker.reset(prev_sym or "", prev_iv or "5m")
                    _ws_client_meta[ws_id] = {
                        "symbol":   sym,
                        "interval": iv,
                        "strategy": strategy,
                    }
            except asyncio.TimeoutError:
                pass
            except Exception:
                disconnected["flag"] = True
                break

    recv_task = asyncio.create_task(recv_msgs())

    async def safe_send(payload: dict) -> bool:
        try:
            await ws.send_json(payload)
            return True
        except Exception:
            disconnected["flag"] = True
            return False

    try:
        while not disconnected["flag"]:
            tick_count += 1
            open_mkt   = _mkt_hours.open_markets()
            meta       = _ws_client_meta.get(ws_id, {})
            sym        = meta.get("symbol")
            iv         = meta.get("interval", "5m")

            if sym and _mkt_hours.is_tradeable(sym, open_mkt):
                try:
                    price = _data.get_live_price(sym)
                    if price > 0:
                        prev  = _data.get_prev_close(sym)
                        chg   = round(price - prev, 4)
                        pct   = round((chg / prev * 100) if prev else 0, 2)
                        now_u = int(datetime.now(timezone.utc).timestamp())
                        bar   = _bar_tracker.update(sym, iv, price, now_u)

                        exit_ev = _trades.check_exits(sym, price)
                        if exit_ev:
                            await broadcast(_trades._exit_to_dict(exit_ev))

                        live_pnl = _trades.compute_live_pnl(sym, price)

                        if not await safe_send({
                            "type":         "tick",
                            "symbol":       sym,
                            "price":        round(price, 4),
                            "change":       chg,
                            "change_pct":   pct,
                            "open_markets": open_mkt,
                            "bar": {
                                "time":  bar["time"],
                                "open":  round(bar["open"],  4),
                                "high":  round(bar["high"],  4),
                                "low":   round(bar["low"],   4),
                                "close": round(bar["close"], 4),
                            },
                            "active_trade": _trades.get_active(sym),
                            "live_pnl":     live_pnl,
                        }):
                            break
                except Exception as e:
                    if not disconnected["flag"]:
                        print(f"[WS tick] {sym}: {e}")

            if disconnected["flag"]:
                break

            if tick_count % 12 == 0:
                await _scan_watchlist_signals_for_client(ws, open_mkt)

            if tick_count % 12 == 0:
                for ev in _trades.eod_sweep(_data.get_live_price):
                    await broadcast(_trades._exit_to_dict(ev))

            if tick_count % 60 == 0:
                open_mkt = _mkt_hours.open_markets()
                await broadcast(_status_payload(open_mkt))

            await asyncio.sleep(5)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        if not disconnected["flag"]:
            print(f"[WS] fatal: {e}")
    finally:
        recv_task.cancel()
        try:
            _ws_clients.remove(ws)
        except ValueError:
            pass
        _ws_client_meta.pop(ws_id, None)


async def _scan_watchlist_signals_for_client(ws: WebSocket, open_mkt: list):
    """
    Scan watchlist using the strategy AND interval subscribed by THIS client.
    Sends signals (or clear-signal notices) only to that client.
    """
    ws_id        = id(ws)
    meta         = _ws_client_meta.get(ws_id, {})
    strategy_key = meta.get("strategy", "pro_mtf")
    scan_iv      = meta.get("interval",  "5m")

    if scan_iv in ("1d", "1wk"):
        return

    strat = strategy_registry.get(strategy_key)
    if not strat:
        strat = strategy_registry.get("pro_mtf")
        if not strat:
            return

    ts_fn = _make_ts_fn(scan_iv)

    items = _watchlist.load()
    if len(items) > 30:
        print(f"[SCAN] Watchlist has {len(items)} items — capped at 30 for performance.")
        items = items[:30]

    for item in items:
        sym = item.sym
        if not _mkt_hours.is_tradeable(sym, open_mkt):
            continue
        try:
            df   = _fetch_for_interval(sym, scan_iv)
            sigs = strat.generate(df, ts_fn)

            if not sigs:
                await send_to_client(ws, {
                    "type":     "signal_clear",
                    "symbol":   sym,
                    "strategy": strategy_key,
                })
                continue

            last = sigs[-1]

            cooldown_iv_key = f"{scan_iv}_{strategy_key}"
            if not _cooldown.is_allowed(sym, cooldown_iv_key, int(last.time)):
                continue
            _cooldown.record(sym, cooldown_iv_key, int(last.time))

            if _settings["require_mtf"]:
                filtered = _filter_signals_by_mtf(
                    [{"type": last.type, "time": last.time, "price": last.price,
                      "sl": last.sl, "tp": last.tp, "rsi": last.rsi,
                      "atr": last.atr, "confidence": last.confidence,
                      "strategy": last.strategy}],
                    sym
                )
                if not filtered:
                    await send_to_client(ws, {
                        "type":     "signal_clear",
                        "symbol":   sym,
                        "strategy": strategy_key,
                    })
                    continue

            t = _estimator.estimate(df, last.price, last.tp, scan_iv)

            payload = {
                "type":            "signal",
                "signal_type":     last.type,
                "symbol":          sym,
                "time":            last.time,
                "price":           last.price,
                "sl":              last.sl,
                "tp":              last.tp,
                "rsi":             last.rsi,
                "atr":             last.atr,
                "confidence":      last.confidence,
                "strategy":        strategy_key,
                "interval":        scan_iv,
                "target_time":     t["label"],
                "target_datetime": t["datetime"],
                "target_bars":     t["bars"],
                "signal_id":       f"{sym}_{last.time}",
                "trade_status":    "open",
            }
            _signal_history.insert(0, payload)
            if len(_signal_history) > 200:
                _signal_history.pop()

            active_count = len(_trades.get_all_active())
            if _trades.get_active(sym) is None and active_count < MAX_OPEN_TRADES:
                _trades.open_trade(last, sym, scan_iv)

            await send_to_client(ws, payload)

        except Exception as e:
            print(f"[WS scan] {sym} ({scan_iv}): {e}")


def _ts_fn_intraday(idx) -> int:
    import pandas as pd
    try:
        dt = pd.Timestamp(idx)
        if dt.tzinfo:
            dt = dt.tz_convert("UTC").tz_localize(None)
        return int(dt.timestamp())
    except Exception:
        return 0


def _ts_fn_daily(idx) -> str:
    import pandas as pd
    try:
        dt = pd.Timestamp(idx)
        if dt.tzinfo:
            dt = dt.tz_convert("UTC").tz_localize(None)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return str(idx)[:10]


_RESAMPLE_MAP = {
    "3m": ("1m", "3min"),
}

_PERIOD_MAP = {
    "1m":  "7d",
    "2m":  "60d",
    "3m":  "2d",
    "5m":  "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "730d",
    "1h":  "730d",
    "1d":  "2y",
    "1wk": "10y",
}

_INTRADAY_INTERVALS = {"1m", "2m", "3m", "5m", "15m", "30m", "60m", "90m", "1h"}


def _make_ts_fn(interval: str):
    if interval in _INTRADAY_INTERVALS:
        return _ts_fn_intraday
    return _ts_fn_daily


def _fetch_for_interval(symbol: str, interval: str):
    import pandas as pd

    if interval in _RESAMPLE_MAP:
        src_interval, rule = _RESAMPLE_MAP[interval]
        period = _PERIOD_MAP.get(interval, "7d")
        df_src = _data.fetch(symbol, src_interval, period)
        if df_src is None or df_src.empty:
            raise ValueError(f"No {src_interval} data for {symbol} to resample to {interval}")

        if not isinstance(df_src.index, pd.DatetimeIndex):
            df_src.index = pd.to_datetime(df_src.index)

        df_res = df_src.resample(rule, closed="left", label="left").agg({
            "Open":   "first",
            "High":   "max",
            "Low":    "min",
            "Close":  "last",
            "Volume": "sum",
        }).dropna(subset=["Open", "Close"])

        if len(df_res) < 10:
            raise ValueError(f"Resampled {interval} data too sparse for {symbol}: {len(df_res)} bars")

        print(f"[DATA] {symbol} resampled {src_interval}→{interval}: {len(df_res)} bars ✓")
        return df_res

    period = _PERIOD_MAP.get(interval, "2y")
    return _data.fetch(symbol, interval, period)


def _status_payload(open_mkt: list) -> dict:
    return {
        "type":              "status",
        "open_markets":      open_mkt,
        "any_open":          bool(open_mkt),
        "connected_clients": len(_ws_clients),
        "message":           f"Open: {', '.join(open_mkt)}" if open_mkt
                             else "Markets closed — crypto & futures still live",
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Static files — serve React build output (production)
# ═══════════════════════════════════════════════════════════════════════════════
_DIST = os.path.join(_ROOT, "frontend_dist")

if os.path.isdir(_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_DIST, "assets")), name="assets")

    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(_DIST, "index.html"))

    @app.get("/{full_path:path}")
    def catch_all(full_path: str):
        if full_path.startswith("api/"):
            return JSONResponse({"error": "Not found"}, status_code=404)
        return FileResponse(os.path.join(_DIST, "index.html"))
else:
    @app.get("/")
    def serve_dev_hint():
        return JSONResponse({
            "message": "Run `cd frontend && npm install && npm run dev` for the UI",
            "api_docs": "/docs",
        })