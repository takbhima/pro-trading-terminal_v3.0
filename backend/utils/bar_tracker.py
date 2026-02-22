_INTERVAL_MINUTES = {
    "1m": 1, "2m": 2, "5m": 5, "15m": 15, "30m": 30,
    "60m": 60, "1h": 60, "1d": 1440, "1wk": 10080,
}


def _floor_bar(unix_ts: int, interval_min: int) -> int:
    return (unix_ts // (interval_min * 60)) * (interval_min * 60)


class BarStateTracker:
    def __init__(self):
        self._state: dict[str, dict] = {}

    def update(self, symbol: str, interval: str, price: float, unix_ts: int) -> dict:
        iv_min   = _INTERVAL_MINUTES.get(interval, 5)
        bar_time = _floor_bar(unix_ts, iv_min)
        key      = f"{symbol}_{interval}"
        prev     = self._state.get(key)

        if prev is None or prev["time"] != bar_time:
            open_p = prev["close"] if prev else price
            self._state[key] = {
                "time":  bar_time,
                "open":  open_p,
                "high":  price,
                "low":   price,
                "close": price,
            }
        else:
            bar = self._state[key]
            bar["high"]  = max(bar["high"], price)
            bar["low"]   = min(bar["low"],  price)
            bar["close"] = price

        return dict(self._state[key])

    def reset(self, symbol: str, interval: str) -> None:
        self._state.pop(f"{symbol}_{interval}", None)
