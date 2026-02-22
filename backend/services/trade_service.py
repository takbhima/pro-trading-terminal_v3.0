import pytz
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from backend.interfaces.trade_store import ITradeStore, Trade, TradeExit
from backend.interfaces.strategy    import Signal

_IST = pytz.timezone("Asia/Kolkata")
_EST = pytz.timezone("America/New_York")

_INTERVAL_MINUTES = {
    "1m": 1, "2m": 2, "5m": 5, "15m": 15, "30m": 30,
    "60m": 60, "1h": 60, "1d": 390, "1wk": 1950,
}

_EOD = {
    "NSE":  (_IST, 15, 20),
    "NYSE": (_EST, 15, 55),
}


def _is_nse(sym: str) -> bool:
    return sym.endswith(".NS") or sym.endswith(".BO") or sym in ("^NSEI", "^NSEBANK", "^BSESN")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _elapsed_minutes(entry: datetime) -> float:
    return (_now_utc() - entry).total_seconds() / 60


def _compute_confidence(rsi: float, side: str) -> float:
    dist = max(0.0, rsi - 50.0 if side == "BUY" else 50.0 - rsi)
    return round(min(95.0, 50.0 + dist * 1.8), 1)


class TradeService:
    def __init__(self, store: ITradeStore):
        self._store = store

    def open_trade(self, signal: Signal, symbol: str, interval: str) -> Optional[Trade]:
        if self._store.get_active(symbol):
            return None
        iv_min  = _INTERVAL_MINUTES.get(interval, 5)
        bars    = float(getattr(signal, "target_bars", None) or 5)
        exp_min = bars * iv_min
        trade = Trade(
            symbol                = symbol,
            timeframe             = interval,
            strategy              = signal.strategy,
            side                  = signal.type,
            entry_price           = round(signal.price, 4),
            target_price          = round(signal.tp, 4),
            stop_loss             = round(signal.sl, 4),
            confidence            = _compute_confidence(signal.rsi, signal.type),
            entry_time            = _now_utc(),
            expected_time_minutes = round(exp_min, 1),
            expected_bars         = round(bars, 1),
            rsi                   = round(signal.rsi, 2),
            atr                   = round(signal.atr, 4),
        )
        self._store.save_active(trade)
        return trade

    def check_exits(self, symbol: str, current_price: float) -> Optional[TradeExit]:
        trade = self._store.get_active(symbol)
        if not trade:
            return None
        reason = (
            self._check_target(trade, current_price)
            or self._check_stop(trade, current_price)
            or self._check_time(trade)
            or self._check_eod(symbol)
        )
        if reason:
            return self._close(trade, current_price, reason)
        return None

    def force_close(self, symbol: str, price: float, reason: str = "Manual Close") -> Optional[TradeExit]:
        trade = self._store.get_active(symbol)
        if not trade:
            return None
        return self._close(trade, price, reason)

    def eod_sweep(self, get_price_fn) -> List[TradeExit]:
        exits = []
        for trade in self._store.get_all_active():
            reason = self._check_eod(trade.symbol)
            if reason:
                price = get_price_fn(trade.symbol) or trade.entry_price
                ev = self._close(trade, price, reason)
                if ev:
                    exits.append(ev)
        return exits

    def get_active(self, symbol: str) -> Optional[dict]:
        trade = self._store.get_active(symbol)
        return self._trade_to_dict(trade) if trade else None

    def get_all_active(self) -> List[dict]:
        return [self._trade_to_dict(t) for t in self._store.get_all_active()]

    def get_history(self, symbol: Optional[str] = None) -> List[dict]:
        return [self._exit_to_dict(e) for e in self._store.get_history(symbol)]

    def compute_live_pnl(self, symbol: str, current_price: float) -> Optional[float]:
        trade = self._store.get_active(symbol)
        if not trade:
            return None
        pnl = current_price - trade.entry_price if trade.side == "BUY" else trade.entry_price - current_price
        return round(pnl, 4)

    @staticmethod
    def _check_target(trade, price):
        if trade.side == "BUY"  and price >= trade.target_price: return "Target Hit"
        if trade.side == "SELL" and price <= trade.target_price: return "Target Hit"
        return None

    @staticmethod
    def _check_stop(trade, price):
        if trade.side == "BUY"  and price <= trade.stop_loss: return "Stop Hit"
        if trade.side == "SELL" and price >= trade.stop_loss: return "Stop Hit"
        return None

    @staticmethod
    def _check_time(trade):
        if _elapsed_minutes(trade.entry_time) >= trade.expected_time_minutes:
            return "Time Exit"
        return None

    @staticmethod
    def _check_eod(symbol):
        now = _now_utc()
        tz, h, m = _EOD["NSE"] if _is_nse(symbol) else _EOD["NYSE"]
        local  = now.astimezone(tz)
        cutoff = local.replace(hour=h, minute=m, second=0, microsecond=0)
        if local.weekday() < 5 and local >= cutoff:
            return "EOD Exit"
        return None

    def _close(self, trade, exit_price, reason):
        self._store.remove_active(trade.symbol)
        pnl     = round(exit_price - trade.entry_price if trade.side == "BUY" else trade.entry_price - exit_price, 4)
        pnl_pct = round((pnl / trade.entry_price) * 100, 2) if trade.entry_price else 0
        exit_event = TradeExit(
            symbol           = trade.symbol,
            side             = trade.side,
            strategy         = trade.strategy,
            timeframe        = trade.timeframe,
            entry_price      = trade.entry_price,
            exit_price       = round(exit_price, 4),
            target_price     = trade.target_price,
            stop_loss        = trade.stop_loss,
            exit_reason      = reason,
            pnl              = pnl,
            pnl_pct          = pnl_pct,
            duration_minutes = round(_elapsed_minutes(trade.entry_time), 1),
            entry_time       = trade.entry_time.isoformat(),
            exit_time        = _now_utc().isoformat(),
            confidence       = trade.confidence,
        )
        self._store.save_closed(exit_event)
        return exit_event

    @staticmethod
    def _trade_to_dict(trade) -> dict:
        elapsed = round(_elapsed_minutes(trade.entry_time), 1)
        return {
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
            "elapsed_minutes":       elapsed,
        }

    @staticmethod
    def _exit_to_dict(e) -> dict:
        return {
            "type":             "exit",
            "symbol":           e.symbol,
            "side":             e.side,
            "strategy":         e.strategy,
            "timeframe":        e.timeframe,
            "entry_price":      e.entry_price,
            "exit_price":       e.exit_price,
            "target_price":     e.target_price,
            "stop_loss":        e.stop_loss,
            "exit_reason":      e.exit_reason,
            "pnl":              e.pnl,
            "pnl_pct":          e.pnl_pct,
            "duration_minutes": e.duration_minutes,
            "entry_time":       e.entry_time,
            "exit_time":        e.exit_time,
            "confidence":       e.confidence,
        }
