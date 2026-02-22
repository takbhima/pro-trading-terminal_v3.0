"""
SqliteTradeStore — persistent trade history using SQLite.
Replaces InMemoryTradeStore while satisfying the same ITradeStore interface.
History survives server restarts; active trades are kept in memory for speed.
"""
import sqlite3
import json
import os
from typing import Optional, List
from datetime import datetime, timezone

from backend.interfaces.trade_store import ITradeStore, Trade, TradeExit


_CREATE_HISTORY = """
CREATE TABLE IF NOT EXISTS trade_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol         TEXT    NOT NULL,
    side           TEXT    NOT NULL,
    strategy       TEXT,
    timeframe      TEXT,
    entry_price    REAL,
    exit_price     REAL,
    target_price   REAL,
    stop_loss      REAL,
    exit_reason    TEXT,
    pnl            REAL,
    pnl_pct        REAL,
    duration_minutes REAL,
    entry_time     TEXT,
    exit_time      TEXT,
    confidence     REAL,
    created_at     TEXT DEFAULT (datetime('now'))
);
"""

_CREATE_ACTIVE = """
CREATE TABLE IF NOT EXISTS active_trades (
    symbol      TEXT PRIMARY KEY,
    trade_json  TEXT NOT NULL,
    created_at  TEXT DEFAULT (datetime('now'))
);
"""


def _trade_from_row(row: dict) -> Trade:
    return Trade(
        symbol                = row["symbol"],
        timeframe             = row["timeframe"] or "",
        strategy              = row["strategy"] or "",
        side                  = row["side"],
        entry_price           = row["entry_price"],
        target_price          = row["target_price"],
        stop_loss             = row["stop_loss"],
        confidence            = row["confidence"],
        entry_time            = datetime.fromisoformat(row["entry_time"]),
        expected_time_minutes = row.get("expected_time_minutes", 60),
        expected_bars         = row.get("expected_bars", 5),
        rsi                   = row.get("rsi", 50),
        atr                   = row.get("atr", 0),
    )


class SqliteTradeStore(ITradeStore):
    """
    Persistent SQLite-backed store.
    Active trades → SQLite table (restored on restart).
    Closed trades → SQLite table (permanent history).
    """

    def __init__(self, db_path: str = "trades.db"):
        self._db_path = db_path
        self._conn    = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        # In-memory cache of active trades for fast lookups
        self._active: dict[str, Trade] = self._restore_active()

    # ── Schema ────────────────────────────────────────────────────────────────

    def _init_schema(self):
        with self._conn:
            self._conn.execute(_CREATE_HISTORY)
            self._conn.execute(_CREATE_ACTIVE)

    def _restore_active(self) -> dict[str, Trade]:
        """Restore active trades from SQLite on startup."""
        out: dict[str, Trade] = {}
        try:
            rows = self._conn.execute("SELECT symbol, trade_json FROM active_trades").fetchall()
            for row in rows:
                data = json.loads(row["trade_json"])
                data["entry_time"] = datetime.fromisoformat(data["entry_time"])
                # Remove keys not in Trade's __init__ (e.g. 'status' added at save time)
                known = {"symbol", "timeframe", "strategy", "side", "entry_price",
                         "target_price", "stop_loss", "confidence", "entry_time",
                         "expected_time_minutes", "expected_bars", "rsi", "atr"}
                data = {k: v for k, v in data.items() if k in known}
                try:
                    out[row["symbol"]] = Trade(**data)
                except Exception as e:
                    print(f"[DB] Could not restore trade for {row['symbol']}: {e}")
        except Exception as e:
            print(f"[DB] restore_active error: {e}")
        if out:
            print(f"[DB] Restored {len(out)} active trade(s) from SQLite")
        return out

    # ── ITradeStore interface ──────────────────────────────────────────────────

    def save_active(self, trade: Trade) -> None:
        self._active[trade.symbol] = trade
        data = {
            "symbol":                trade.symbol,
            "timeframe":             trade.timeframe,
            "strategy":              trade.strategy,
            "side":                  trade.side,
            "entry_price":           trade.entry_price,
            "target_price":          trade.target_price,
            "stop_loss":             trade.stop_loss,
            "confidence":            trade.confidence,
            "entry_time":            trade.entry_time.isoformat(),
            "expected_time_minutes": trade.expected_time_minutes,
            "expected_bars":         trade.expected_bars,
            "rsi":                   trade.rsi,
            "atr":                   trade.atr,
            "status":                trade.status,
        }
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO active_trades (symbol, trade_json) VALUES (?, ?)",
                (trade.symbol, json.dumps(data)),
            )

    def get_active(self, symbol: str) -> Optional[Trade]:
        return self._active.get(symbol)

    def get_all_active(self) -> List[Trade]:
        return list(self._active.values())

    def remove_active(self, symbol: str) -> Optional[Trade]:
        trade = self._active.pop(symbol, None)
        with self._conn:
            self._conn.execute("DELETE FROM active_trades WHERE symbol = ?", (symbol,))
        return trade

    def save_closed(self, exit: TradeExit) -> None:
        with self._conn:
            self._conn.execute(
                """INSERT INTO trade_history
                   (symbol, side, strategy, timeframe, entry_price, exit_price,
                    target_price, stop_loss, exit_reason, pnl, pnl_pct,
                    duration_minutes, entry_time, exit_time, confidence)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    exit.symbol, exit.side, exit.strategy, exit.timeframe,
                    exit.entry_price, exit.exit_price, exit.target_price,
                    exit.stop_loss, exit.exit_reason, exit.pnl, exit.pnl_pct,
                    exit.duration_minutes, exit.entry_time, exit.exit_time,
                    exit.confidence,
                ),
            )

    def get_history(self, symbol: Optional[str] = None) -> List[TradeExit]:
        if symbol:
            rows = self._conn.execute(
                "SELECT * FROM trade_history WHERE symbol=? ORDER BY exit_time DESC LIMIT 100",
                (symbol,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM trade_history ORDER BY exit_time DESC LIMIT 200"
            ).fetchall()
        return [self._row_to_exit(r) for r in rows]

    # ── Analytics extras ──────────────────────────────────────────────────────

    def get_pnl_summary(self) -> dict:
        """Returns aggregate PnL stats — not part of ITradeStore but useful."""
        row = self._conn.execute(
            """SELECT
                COUNT(*)                                  AS total,
                SUM(CASE WHEN pnl >= 0 THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN pnl < 0  THEN 1 ELSE 0 END) AS losses,
                ROUND(SUM(pnl), 4)                        AS total_pnl,
                ROUND(AVG(pnl), 4)                        AS avg_pnl,
                ROUND(MAX(pnl), 4)                        AS best,
                ROUND(MIN(pnl), 4)                        AS worst
               FROM trade_history"""
        ).fetchone()
        if not row or row["total"] == 0:
            return {"total": 0, "wins": 0, "losses": 0, "win_rate": 0,
                    "total_pnl": 0, "avg_pnl": 0, "best": 0, "worst": 0}
        return {
            "total":     row["total"],
            "wins":      row["wins"],
            "losses":    row["losses"],
            "win_rate":  round(row["wins"] / row["total"] * 100, 1),
            "total_pnl": row["total_pnl"],
            "avg_pnl":   row["avg_pnl"],
            "best":      row["best"],
            "worst":     row["worst"],
        }

    @staticmethod
    def _row_to_exit(row) -> TradeExit:
        return TradeExit(
            symbol           = row["symbol"],
            side             = row["side"],
            strategy         = row["strategy"] or "",
            timeframe        = row["timeframe"] or "",
            entry_price      = row["entry_price"] or 0.0,
            exit_price       = row["exit_price"]  or 0.0,
            target_price     = row["target_price"] or 0.0,
            stop_loss        = row["stop_loss"]    or 0.0,
            exit_reason      = row["exit_reason"]  or "",
            pnl              = row["pnl"]          or 0.0,
            pnl_pct          = row["pnl_pct"]      or 0.0,
            duration_minutes = row["duration_minutes"] or 0.0,
            entry_time       = row["entry_time"]   or "",
            exit_time        = row["exit_time"]    or "",
            confidence       = row["confidence"]   or 0.0,
        )
