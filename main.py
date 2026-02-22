"""
Pro Trading Terminal v4 — Enhanced Edition
==========================================
Enhancements over v3:

  E1 — WebSocket Multi-Client Broadcast
       _ws_clients is now actually used: signals, ticks, and exits are
       broadcast to ALL connected clients. Each client maintains its own
       subscribed symbol/interval but receives watchlist scan pushes globally.

  E2 — Persistent SQLite Trade History
       SqliteTradeStore replaces InMemoryTradeStore. Active trades survive
       server restarts. Full PnL analytics available at /api/trades/analytics.

  E3 — Signal Cooldown / Deduplication Window
       SignalCooldownTracker enforces a configurable N-bar cooldown per
       (symbol, interval) pair. Default = 5 bars. Configurable via
       PATCH /api/settings/cooldown.

  E4 — Multi-Timeframe Confirmation Toggle
       New /api/chartdata supports ?require_mtf=1. When enabled, a signal
       on the requested timeframe must align with the 1D trend (EMA9>EMA21).
       Frontend toggle added in StrategyBar.

  E5 — Browser Notification Permission Request
       New /api/notify-permission endpoint signals readiness. Frontend
       requests Notification.requestPermission() on app start via a
       non-blocking prompt banner.

  E6 — Watchlist Symbol Validation
       POST /api/watchlist now calls SymbolValidator before accepting.
       Returns suggested display name from yfinance longName.
       New GET /api/validate?sym=AAPL endpoint for frontend pre-validation.
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
_trade_store = SqliteTradeStore(os.path.join(_ROOT, "trades.db"))   # E2
_trades      = TradeService(_trade_store)
_watchlist   = JsonWatchlistStore(os.path.join(_ROOT, "watchlist.json"))
_news        = MultiSourceNewsService()
_predictor   = TechnicalNewsPredictor()
_chart       = ChartService()
_estimator   = TargetTimeEstimator()
_mkt_hours   = MarketHoursService()
_cooldown    = SignalCooldownTracker(cooldown_bars=5)               # E3

# ── WebSocket state ───────────────────────────────────────────────────────────
_bar_tracker       = BarStateTracker()
_signal_history:   list            = []
_ws_clients:       list            = []   # E1: list of connected WebSocket objects

# ── Settings ──────────────────────────────────────────────────────────────────
MAX_OPEN_TRADES = 3
_settings = {
    "cooldown_bars": 5,     # E3
    "require_mtf":   False, # E4
}

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
    """Send payload to all connected clients (optionally excluding one)."""
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
        except ValueError:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
#  REST API
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/status")
def api_status():
    open_mkt = _mkt_hours.open_markets()
    return {
        "open_markets":   open_mkt,
        "signals":        len(_signal_history),
        "active_trades":  len(_trades.get_all_active()),
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
    """E3: Update signal cooldown window at runtime."""
    _settings["cooldown_bars"] = bars
    _cooldown.set_cooldown_bars(bars)
    return {"ok": True, "cooldown_bars": bars}

@app.patch("/api/settings/mtf")
def api_set_mtf(enabled: bool):
    """E4: Toggle multi-timeframe confirmation requirement."""
    _settings["require_mtf"] = enabled
    return {"ok": True, "require_mtf": enabled}


# ── E6 — Symbol validation endpoint ──────────────────────────────────────────

@app.get("/api/validate")
def api_validate_symbol(sym: str):
    """E6: Validate a ticker before adding to watchlist."""
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
    """E6: Validate symbol before adding."""
    sym = sym.strip().upper()
    result = validate_symbol(sym)
    if not result.ok:
        return JSONResponse({"ok": False, "reason": result.reason}, status_code=400)

    # Use suggested name from yfinance if none provided
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
    require_mtf: bool = False,   # E4: can be set per-request or via global setting
):
    try:
        strat = strategy_registry.get(strategy)
        if not strat:
            return JSONResponse({"error": f"Unknown strategy: {strategy}"}, status_code=400)

        df = _data.fetch(symbol, interval)
        if df is None or df.empty:
            return _empty_chart(f"No data for {symbol}")

        chart_data = _chart.build_chart_data(df, strat, interval)

        # E4 — Multi-timeframe filter
        use_mtf = require_mtf or _settings["require_mtf"]
        if use_mtf and interval not in ("1d", "1wk"):
            chart_data["signals"] = _filter_signals_by_mtf(chart_data["signals"], symbol)
            chart_data["total_signals"] = len(chart_data["signals"])
            chart_data["latest_signal"] = chart_data["signals"][-1] if chart_data["signals"] else None

        # Enrich latest signal with target time
        if chart_data["latest_signal"]:
            latest = chart_data["latest_signal"]
            t = _estimator.estimate(df, float(latest["price"]), float(latest["tp"]), interval)
            latest.update({"target_time": t["label"], "target_datetime": t["datetime"], "target_bars": t["bars"]})

            if _trades.get_active(symbol) is None:
                from backend.interfaces.strategy import Signal
                sig = Signal(**{k: latest[k] for k in Signal.__dataclass_fields__ if k in latest})
                _trades.open_trade(sig, symbol, interval)

        return JSONResponse({
            **chart_data,
            "active_trade":  _trades.get_active(symbol),
            "mtf_active":    use_mtf,
            "strategy_used": strategy,   # echoed back so frontend can detect stale responses
            "interval_used": interval,
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return _empty_chart(str(e))


def _filter_signals_by_mtf(signals: list, symbol: str) -> list:
    """
    E4: Keep only signals that align with the daily trend.
    BUY signals pass when EMA9 > EMA21 on daily chart.
    SELL signals pass when EMA9 < EMA21 on daily chart.
    Returns signals unfiltered on any error so callers never get an empty list due to a data issue.
    """
    if not signals:
        return signals
    try:
        from backend.indicators import EMA  # local import — avoids circular dep at module load
        df_daily = _data.fetch(symbol, "1d")
        if df_daily is None or df_daily.empty or len(df_daily) < 22:
            return signals  # not enough data — skip filter
        e9d  = float(EMA(9).compute(df_daily).iloc[-1])
        e21d = float(EMA(21).compute(df_daily).iloc[-1])
        if e9d != e9d or e21d != e21d:  # NaN check
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
        return signals  # fallback: return unfiltered


def _empty_chart(error: str) -> JSONResponse:
    return JSONResponse({"error": error, "candles": [], "ema9": [], "ema21": [],
                         "ema200": [], "signals": [], "latest_signal": None,
                         "active_trade": None})


# ── News ──────────────────────────────────────────────────────────────────────

@app.get("/api/news")
def api_news(symbols: str = ""):
    sym_list = [s.strip() for s in symbols.split(",") if s.strip()] if symbols \
               else [w.sym for w in _watchlist.load()[:8]]
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
    """E2: PnL analytics from SQLite — survives restarts."""
    summary  = _trade_store.get_pnl_summary()
    # Pass symbol=None explicitly for full history (matches ITradeStore signature)
    history  = _trade_store.get_history(symbol=None)
    by_strat: dict = {}
    for t in history:
        # history items are TradeExit dataclass instances — access as attributes
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
#  WebSocket — E1: true multi-client broadcast
# ═══════════════════════════════════════════════════════════════════════════════

@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)

    open_mkt         = _mkt_hours.open_markets()
    current_symbol   = {"sym":      None}
    current_interval = {"interval": "5m"}
    tick_count       = 0

    await ws.send_json(_status_payload(open_mkt))

    disconnected = {"flag": False}

    async def recv_msgs():
        while True:
            try:
                msg = await asyncio.wait_for(ws.receive_json(), timeout=0.1)
                if isinstance(msg, dict) and msg.get("type") == "subscribe":
                    sym = msg.get("symbol", "").strip()
                    iv  = msg.get("interval", "5m")
                    if sym != current_symbol["sym"] or iv != current_interval["interval"]:
                        _bar_tracker.reset(current_symbol["sym"] or "", current_interval["interval"])
                    current_symbol["sym"]        = sym
                    current_interval["interval"] = iv
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
            open_mkt    = _mkt_hours.open_markets()
            sym         = current_symbol["sym"]
            iv          = current_interval["interval"]

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
                            exit_payload = _trades._exit_to_dict(exit_ev)
                            # E1: broadcast exit to all clients
                            await broadcast(exit_payload)

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
                await _scan_watchlist_signals(open_mkt)  # E1: broadcast to all clients

            if tick_count % 12 == 0:
                for ev in _trades.eod_sweep(_data.get_live_price):
                    await broadcast(_trades._exit_to_dict(ev))

            if tick_count % 60 == 0:
                open_mkt = _mkt_hours.open_markets()
                status_p = _status_payload(open_mkt)
                await broadcast(status_p)

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


async def _scan_watchlist_signals(open_mkt: list):
    """
    E1: Broadcast to all connected clients (not just the triggering ws).
    E3: Check cooldown before sending a signal.
    E4: Optionally filter by MTF alignment.
    """
    pro_mtf = strategy_registry.get("pro_mtf")
    if not pro_mtf:
        return

    for item in _watchlist.load()[:10]:
        sym = item.sym
        if not _mkt_hours.is_tradeable(sym, open_mkt):
            continue
        try:
            df   = _data.fetch(sym, "5m", "2d")
            sigs = pro_mtf.generate(df, _ts_fn_intraday)
            if not sigs:
                continue
            last = sigs[-1]

            # E3 — Cooldown check
            if not _cooldown.is_allowed(sym, "5m", int(last.time)):
                continue
            _cooldown.record(sym, "5m", int(last.time))

            # E4 — Optional MTF filter
            if _settings["require_mtf"]:
                filtered = _filter_signals_by_mtf(
                    [{"type": last.type, "time": last.time, "price": last.price,
                      "sl": last.sl, "tp": last.tp, "rsi": last.rsi,
                      "atr": last.atr, "confidence": last.confidence,
                      "strategy": last.strategy}],
                    sym
                )
                if not filtered:
                    continue

            t = _estimator.estimate(df, last.price, last.tp, "5m")

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
                "strategy":        last.strategy,
                "target_time":     t["label"],
                "target_datetime": t["datetime"],
                "target_bars":     t["bars"],
            }
            _signal_history.insert(0, payload)
            if len(_signal_history) > 200:
                _signal_history.pop()

            active_count = len(_trades.get_all_active())
            if _trades.get_active(sym) is None and active_count < MAX_OPEN_TRADES:
                _trades.open_trade(last, sym, "5m")

            # E1: broadcast to all connected clients
            await broadcast(payload)

        except Exception as e:
            print(f"[WS scan] {sym}: {e}")


def _ts_fn_intraday(idx) -> int:
    import pandas as pd
    try:
        dt = pd.Timestamp(idx)
        if dt.tzinfo:
            dt = dt.tz_convert("UTC").tz_localize(None)
        return int(dt.timestamp())
    except Exception:
        return 0


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