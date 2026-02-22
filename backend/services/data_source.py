import time
import pandas as pd
import yfinance as yf

from backend.interfaces import IDataSource

_PERIOD_MAP = {
    "1m":  "7d",
    "2m":  "7d",
    "5m":  "60d",
    "15m": "60d",
    "30m": "60d",
    "60m": "730d",
    "1h":  "730d",
    "1d":  "2y",
    "1wk": "10y",
}


class YFinanceDataSource(IDataSource):
    def fetch(self, symbol: str, interval: str, period: str = None) -> pd.DataFrame:
        resolved_period = period or _PERIOD_MAP.get(interval, "2y")
        df = self._try_ticker(symbol, interval, resolved_period)
        if df is not None and len(df) > 50:
            return df
        df = self._try_download(symbol, interval, resolved_period)
        if df is not None and len(df) > 50:
            return df
        raise ValueError(f"No data returned for {symbol} after all attempts")

    def get_live_price(self, symbol: str) -> float:
        try:
            info = yf.Ticker(symbol).fast_info
            return float(
                getattr(info, "last_price", None)
                or getattr(info, "regular_market_price", None)
                or 0
            )
        except Exception:
            return 0.0

    def get_prev_close(self, symbol: str) -> float:
        try:
            info = yf.Ticker(symbol).fast_info
            return float(getattr(info, "previous_close", 0) or 0)
        except Exception:
            return 0.0

    def _try_ticker(self, symbol, interval, period):
        try:
            df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
            return self._clean(df, symbol, "Ticker")
        except Exception as e:
            print(f"[DATA] Ticker failed {symbol}: {e}")
            return None

    def _try_download(self, symbol, interval, period):
        for attempt in range(3):
            try:
                df = yf.download(symbol, period=period, interval=interval,
                                 progress=False, auto_adjust=True, timeout=20)
                result = self._clean(df, symbol, "download")
                if result is not None and len(result) > 50:
                    return result
                time.sleep(2)
            except Exception as e:
                print(f"[DATA] download attempt {attempt+1} {symbol}: {e}")
                time.sleep(2)
        return None

    @staticmethod
    def _clean(df, symbol, source):
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if "Adj Close" in df.columns and "Close" not in df.columns:
            df.rename(columns={"Adj Close": "Close"}, inplace=True)
        required = ["Open", "High", "Low", "Close"]
        if not all(c in df.columns for c in required):
            return None
        df = df.dropna(subset=required).copy()
        print(f"[DATA] {symbol} {source}: {len(df)} bars ✓")
        return df
