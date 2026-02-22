"""
Pro Trading Terminal v2 — SOLID Edition
========================================
main.py is the composition root: the only place that knows which concrete
implementations to wire together.  All other modules depend on abstractions.

Frontend: React + Vite (see frontend/)
  - Development:  cd frontend && npm run dev   (proxied to :8000)
  - Production:   cd frontend && npm run build  → frontend_dist/

BUG FIXES in this version:
  1. Removed duplicate recv_msgs definition — first definition never set
     disconnected["flag"], causing the tick loop to hang after client
     disconnect and leak the coroutine.
  2. EOD sweep now runs every tick_count % 12 (every ~60s) instead of
     tick_count % 60 (every ~5 minutes), preventing missed NSE 3:20 PM cutoffs.
  3. Watchlist signal scan now caps simultaneous open trades at MAX_OPEN_TRADES
     (default 3) to prevent opening a trade on every watchlist symbol at once.
"""

import asyncio, os
from datetime import datetime, timezone

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# ── Concrete implementations (chosen ONLY here — composition root) ──────────
from backend.repositories import InMemoryTradeStore, JsonWatchlistStore
from backend.services import (
    YFinanceDataSource,
    TradeService,
    MultiSourceNewsService,
    TechnicalNewsPredictor,
    ChartService,
    TargetTimeEstimator,
    MarketHoursService,
)
from backend.strategies import registry as strategy_registry

# ── Wire up all dependencies ─────────────────────────────────────────────────
_ROOT        = os.path.dirname(__file__)
_data        = YFinanceDataSource()
_trade_store = InMemoryTradeStore()
_trades      = TradeService(_trade_store)
_watchlist   = JsonWatchlistStore(os.path.join(_ROOT, "watchlist.json"))
_news        = MultiSourceNewsService()
_predictor   = TechnicalNewsPredictor()
_chart       = ChartService()
_estimator   = TargetTimeEstimator()
_mkt_hours   = MarketHoursService()

# ── Max simultaneous open trades from watchlist scan (Bug 5 fix) ─────────────
MAX_OPEN_TRADES = 3

# ── WebSocket state (not a service — purely transport-layer state) ───────────
from backend.utils import BarStateTracker
_bar_tracker      = BarStateTracker()
_signal_history:  list                = []
_last_signal_key: dict[str, str]      = {}
_ws_clients:      list                = []

app = FastAPI(title="Pro Trading Terminal v2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════════
#  REST API
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/status")
def api_status():
    open_mkt = _mkt_hours.open_markets()
    return {
        "open_markets":  open_mkt,
        "signals":       len(_signal_history),
        "active_trades": len(_trades.get_all_active()),
    }

@app.get("/api/strategies")
def api_strategies():
    return strategy_registry.to_list()

# ── Watchlist ─────────────────────────────────────────────────────────────────
@app.get("/api/watchlist")
def api_get_watchlist():
    return [{"sym": w.sym, "name": w.name} for w in _watchlist.load()]

@app.post("/api/watchlist")
def api_add_watchlist(sym: str, name: str = ""):
    return _watchlist.add(sym, name)

@app.delete("/api/watchlist/{sym}")
def api_del_watchlist(sym: str):
    return _watchlist.remove(sym)

# ── Chart data ────────────────────────────────────────────────────────────────
@app.get("/api/chartdata")
def api_chartdata(symbol: str, interval: str = "1d", strategy: str = "pro_mtf"):
    try:
        strat = strategy_registry.get(strategy)
        if not strat:
            return JSONResponse({"error": f"Unknown strategy: {strategy}"}, status_code=400)

        df = _data.fetch(symbol, interval)
        if df is None or df.empty:
            return _empty_chart(f"No data for {symbol}")

        chart_data = _chart.build_chart_data(df, strat, interval)

        # Enrich latest signal with target time
        if chart_data["latest_signal"]:
            latest = chart_data["latest_signal"]
            t = _estimator.estimate(df, float(latest["price"]), float(latest["tp"]), interval)
            latest.update({"target_time": t["label"], "target_datetime": t["datetime"], "target_bars": t["bars"]})

            # Open trade if none active
            if _trades.get_active(symbol) is None:
                from backend.interfaces.strategy import Signal
                sig = Signal(**{k: latest[k] for k in Signal.__dataclass_fields__ if k in latest})
                _trades.open_trade(sig, symbol, interval)

        return JSONResponse({
            **chart_data,
            "active_trade": _trades.get_active(symbol),
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return _empty_chart(str(e))


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


# ═══════════════════════════════════════════════════════════════════════════════
#  WebSocket
#
#  BUG FIX 1 (recv_msgs duplicate): The original code defined recv_msgs twice.
#  The first definition was the one captured by asyncio.create_task(), and it
#  never set disconnected["flag"], so the outer tick loop had no way to know
#  the client was gone. Coroutines leaked and the loop ran forever consuming
#  CPU. Fixed by keeping only one correct definition that always sets the flag.
#
#  BUG FIX 2 (EOD sweep frequency): EOD sweep moved from tick_count % 60
#  (~5 min) to tick_count % 12 (~60s) so the 3:20 PM NSE cutoff is never
#  missed by more than 60 seconds.
#
#  BUG FIX 3 (uncapped trade opens): _scan_watchlist_signals now checks
#  len(_trades.get_all_active()) against MAX_OPEN_TRADES before opening a
#  new position, preventing simultaneous trades on every watchlist symbol.
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

    # FIX 1: Single, correct recv_msgs definition.
    # Always sets disconnected["flag"] on any exception (including clean close).
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
                # Normal — no message in this 100ms window, keep looping
                pass
            except Exception:
                # Client disconnected or WS closed — signal tick loop to stop
                disconnected["flag"] = True
                break

    recv_task = asyncio.create_task(recv_msgs())

    async def safe_send(payload: dict) -> bool:
        """Send JSON; returns False if the connection is gone so caller can break."""
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
                            if not await safe_send(_trades._exit_to_dict(exit_ev)):
                                break

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

            # Scan watchlist for signals every ~60s (tick_count % 12, sleep=5s)
            if tick_count % 12 == 0:
                await _scan_watchlist_signals(ws, open_mkt)

            # FIX 2: EOD sweep now every ~60s (was every ~5 min).
            # Status broadcast kept at ~5 min to avoid spam.
            if tick_count % 12 == 0:
                for ev in _trades.eod_sweep(_data.get_live_price):
                    if not await safe_send(_trades._exit_to_dict(ev)):
                        break

            if tick_count % 60 == 0:
                open_mkt = _mkt_hours.open_markets()
                if not await safe_send(_status_payload(open_mkt)):
                    break

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


async def _scan_watchlist_signals(ws: WebSocket, open_mkt: list):
    """Scan watchlist with Pro MTF on 5m for push signals.

    BUG FIX (signal_type): use `signal_type` instead of `type` for BUY/SELL
    direction to avoid collision with the WS message type field.

    BUG FIX (uncapped trades): Check total open trade count against
    MAX_OPEN_TRADES before opening. This prevents the scanner from flooding
    the trade store with one open position per watchlist symbol every cycle.
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
            last    = sigs[-1]
            sig_key = f"{sym}_{last.time}"
            if _last_signal_key.get(sym) == sig_key:
                continue
            _last_signal_key[sym] = sig_key

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

            # FIX 3: Only open a new trade if we are below the cap AND this
            # symbol doesn't already have one. Without the cap, every watchlist
            # symbol gets a trade opened simultaneously each scan cycle.
            active_count = len(_trades.get_all_active())
            if _trades.get_active(sym) is None and active_count < MAX_OPEN_TRADES:
                _trades.open_trade(last, sym, "5m")

            await ws.send_json(payload)
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
        "type":         "status",
        "open_markets": open_mkt,
        "any_open":     bool(open_mkt),
        "message":      f"Open: {', '.join(open_mkt)}" if open_mkt
                        else "Markets closed — crypto & futures still live",
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  Static files — serve React build output (production)
#  For development: run `cd frontend && npm run dev` (Vite proxies to :8000)
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
        index = os.path.join(_DIST, "index.html")
        return FileResponse(index)
else:
    @app.get("/")
    def serve_dev_hint():
        return JSONResponse({
            "message": "Run `cd frontend && npm install && npm run dev` for the UI",
            "api_docs": "/docs",
        })