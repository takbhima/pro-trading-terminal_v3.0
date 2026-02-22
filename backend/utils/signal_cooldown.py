"""
SignalCooldownTracker — prevents the same symbol from firing repeated signals
within a configurable cooldown window (in bars).

Problem: _last_signal_key only suppresses the *exact* same bar timestamp.
If price revisits the same zone 5 candles later, a fresh signal fires.

Solution: record the bar-time of each signal per symbol and reject new signals
that arrive within `cooldown_bars` bars on the same timeframe.
"""
import time
from typing import Dict, Tuple, Optional


class SignalCooldownTracker:
    """
    Tracks the last signal time per (symbol, interval) pair.
    A new signal is accepted only if at least `cooldown_bars` bars have
    elapsed since the last accepted signal.

    Interval minutes mapping used to convert bars → seconds:
        1m→60, 2m→120, 5m→300, 15m→900, 30m→1800, 60m/1h→3600,
        1d→23400 (6.5 trading hours), 1wk→117000
    """

    _INTERVAL_SECONDS: Dict[str, int] = {
        "1m":  60,
        "2m":  120,
        "5m":  300,
        "15m": 900,
        "30m": 1800,
        "60m": 3600,
        "1h":  3600,
        "1d":  23400,
        "1wk": 117000,
    }

    def __init__(self, cooldown_bars: int = 5):
        self._cooldown_bars = cooldown_bars
        # key → (last_signal_unix_ts, last_bar_ts_from_signal)
        self._last: Dict[str, Tuple[float, int]] = {}

    def is_allowed(self, symbol: str, interval: str, bar_ts: int) -> bool:
        """
        Returns True if a new signal for (symbol, interval) is permitted.
        bar_ts is the integer UNIX timestamp of the signal's candle.
        """
        key = f"{symbol}_{interval}"
        if key not in self._last:
            return True

        _, last_bar_ts = self._last[key]
        iv_secs   = self._INTERVAL_SECONDS.get(interval, 300)
        min_delta = iv_secs * self._cooldown_bars

        return (bar_ts - last_bar_ts) >= min_delta

    def record(self, symbol: str, interval: str, bar_ts: int) -> None:
        """Mark this (symbol, interval) as having just fired a signal at bar_ts."""
        key = f"{symbol}_{interval}"
        self._last[key] = (time.time(), bar_ts)

    def reset(self, symbol: str, interval: Optional[str] = None) -> None:
        """Clear cooldown state for a symbol (all intervals, or a specific one)."""
        if interval:
            self._last.pop(f"{symbol}_{interval}", None)
        else:
            for k in list(self._last.keys()):
                if k.startswith(f"{symbol}_"):
                    del self._last[k]

    def set_cooldown_bars(self, bars: int) -> None:
        """Update cooldown window at runtime."""
        self._cooldown_bars = max(1, bars)

    @property
    def cooldown_bars(self) -> int:
        return self._cooldown_bars
