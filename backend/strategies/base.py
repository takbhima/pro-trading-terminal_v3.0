import pandas as pd
from backend.interfaces.strategy import IStrategy, Signal


class BaseStrategy(IStrategy):
    def _build_signal(self, df, i, sig_type, atr_series, rsi_series, ts_fn) -> Signal:
        close      = float(df["Close"].iloc[i])
        atr_val    = float(atr_series.iloc[i])
        rsi_val    = float(rsi_series.iloc[i])
        dist       = max(0.0, (rsi_val - 50.0) if sig_type == "BUY" else (50.0 - rsi_val))
        confidence = round(min(95.0, 50.0 + dist * 1.8), 1)

        return Signal(
            time       = ts_fn(df.index[i]),
            type       = sig_type,
            price      = round(close, 4),
            sl         = round(close - atr_val, 4) if sig_type == "BUY" else round(close + atr_val, 4),
            tp         = round(close + atr_val * 2.0, 4) if sig_type == "BUY" else round(close - atr_val * 2.0, 4),
            rsi        = round(rsi_val, 2),
            atr        = round(atr_val, 4),
            confidence = confidence,
            strategy   = self.key,
        )
