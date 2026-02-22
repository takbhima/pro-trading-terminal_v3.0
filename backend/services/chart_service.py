from typing import List
import pandas as pd

from backend.indicators import EMA
from backend.interfaces import IStrategy

_INTRADAY = {"1m", "2m", "5m", "15m", "30m", "60m", "1h"}


def _ts_format(idx, intraday: bool):
    try:
        dt = pd.Timestamp(idx)
        if intraday:
            if dt.tzinfo:
                dt = dt.tz_convert("UTC").tz_localize(None)
            return int(dt.timestamp())
        else:
            if dt.tzinfo:
                dt = dt.tz_convert("UTC").tz_localize(None)
            return dt.strftime("%Y-%m-%d")
    except Exception:
        return str(idx)[:10]


class ChartService:
    def build_chart_data(self, df: pd.DataFrame, strategy: IStrategy, interval: str) -> dict:
        intraday = interval in _INTRADAY
        ts_fn    = lambda idx: _ts_format(idx, intraday)

        df = df.copy()
        df["_e9"]   = EMA(9).compute(df)
        df["_e21"]  = EMA(21).compute(df)
        df["_e200"] = EMA(200).compute(df)
        df.dropna(subset=["Open", "High", "Low", "Close"], inplace=True)

        candles = [
            {
                "time":  ts_fn(i),
                "open":  round(float(r.Open),  4),
                "high":  round(float(r.High),  4),
                "low":   round(float(r.Low),   4),
                "close": round(float(r.Close), 4),
            }
            for i, r in df.iterrows()
        ]

        ema9   = [{"time": ts_fn(i), "value": round(float(r._e9),   4)} for i, r in df.iterrows() if pd.notna(r._e9)]
        ema21  = [{"time": ts_fn(i), "value": round(float(r._e21),  4)} for i, r in df.iterrows() if pd.notna(r._e21)]
        ema200 = [{"time": ts_fn(i), "value": round(float(r._e200), 4)} for i, r in df.iterrows() if pd.notna(r._e200)]

        signals = strategy.generate(df, ts_fn)

        sig_dicts = [
            {
                "time":       s.time,
                "type":       s.type,
                "price":      s.price,
                "sl":         s.sl,
                "tp":         s.tp,
                "rsi":        s.rsi,
                "atr":        s.atr,
                "confidence": s.confidence,
                "strategy":   s.strategy,
                **({"target_time":     s.target_time}     if s.target_time     else {}),
                **({"target_datetime": s.target_datetime} if s.target_datetime else {}),
                **({"target_bars":     s.target_bars}     if s.target_bars     else {}),
            }
            for s in signals
        ]

        return {
            "candles":       candles,
            "ema9":          ema9,
            "ema21":         ema21,
            "ema200":        ema200,
            "signals":       sig_dicts,
            "latest_signal": sig_dicts[-1] if sig_dicts else None,
            "total_signals": len(sig_dicts),
        }
