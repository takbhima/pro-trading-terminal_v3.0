from datetime import datetime, timedelta
import pandas as pd

from backend.indicators import ATR

_INTERVAL_MINUTES = {
    "1m": 1, "2m": 2, "5m": 5, "15m": 15, "30m": 30,
    "60m": 60, "1h": 60, "1d": 390, "1wk": 1950,
}


class TargetTimeEstimator:
    def estimate(self, df: pd.DataFrame, entry: float, tp: float, interval: str) -> dict:
        atr_series  = ATR(14).compute(df)
        atr_per_bar = float(atr_series.iloc[-20:].mean())
        if atr_per_bar <= 0:
            atr_per_bar = abs(tp - entry) * 0.1

        distance   = abs(tp - entry)
        bars_est   = max(1.0, (distance / atr_per_bar) * 1.4)
        mins_per   = _INTERVAL_MINUTES.get(interval, 60)
        total_mins = bars_est * mins_per

        label = self._label(total_mins)
        dt    = self._target_dt(total_mins)
        fmt   = "%d %b %H:%M" if interval not in ("1d", "1wk") else "%d %b %Y"
        return {
            "label":    label,
            "datetime": dt.strftime(fmt),
            "bars":     round(bars_est, 1),
        }

    @staticmethod
    def _label(mins: float) -> str:
        if   mins <=  15:  return f"~{max(5, int(mins))} mins"
        elif mins <=  60:  return f"~{int(mins)} mins"
        elif mins <= 120:  return f"~{mins/60:.1f} hours"
        elif mins <= 390:  return "by end of day"
        elif mins <= 780:  return f"~{mins/390:.1f} trading days"
        elif mins <= 1950: return f"~{int(mins/390)} trading days"
        else:              return f"~{int(mins/1950)} weeks"

    @staticmethod
    def _target_dt(mins: float) -> datetime:
        dt = datetime.now() + timedelta(minutes=mins)
        for _ in range(7):
            if dt.weekday() < 5:
                break
            dt += timedelta(days=1)
        return dt
