import time
import pandas as pd
import yfinance as yf

from backend.interfaces import IDataSource

_PERIOD_MAP = {
    "1m":  "1d",
    "2m":  "5d",
    "5m":  "5d",
    "15m": "10d",
    "30m": "20d",
    "60m": "60d",
    "1h":  "60d",
    "1d":  "2y",
    "1wk": "10y",
}

_MAX_BARS = {
    "1m":  500,
    "2m":  500,
    "5m":  1000,
    "15m": 1000,
    "30m": 800,
    "60m": 600,
    "1h":  600,
    "1d":  1000,
    "1wk": 500,
}

# Per-interval minimum bars required before we accept data.
# NSE 1m data is inherently sparse (13-29 bars) due to yfinance API limits.
# Setting 1m/2m very low so valid sparse data is accepted instead of rejected.
_MIN_BARS = {
    "1m":  5,
    "2m":  5,
    "5m":  10,
    "15m": 10,
    "30m": 20,
    "60m": 30,
    "1h":  30,
    "1d":  50,
    "1wk": 20,
}


class YFinanceDataSource(IDataSource):
    def fetch(self, symbol: str, interval: str, period: str = None) -> pd.DataFrame:
        min_bars = _MIN_BARS.get(interval, 50)
        resolved_period = period or _PERIOD_MAP.get(interval, "2y")

        df = self._try_ticker(symbol, interval, resolved_period)
        if df is not None and len(df) >= min_bars:
            return self._cap_bars(df, interval)

        df2 = self._try_download(symbol, interval, resolved_period)
        if df2 is not None and len(df2) >= min_bars:
            return self._cap_bars(df2, interval)

        # Graceful fallback: if we have SOME data (but below min_bars threshold),
        # return it anyway with a warning rather than crashing.
        # This handles NSE indices/stocks on 1m which only return 13-29 bars.
        best = df if (df is not None and len(df) > 0) else df2
        if best is not None and len(best) > 0:
            print(f"[DATA] {symbol} {interval}: sparse data ({len(best)} bars) "
                  f"— below min {min_bars}, using anyway")
            return self._cap_bars(best, interval)

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
            if df is None:
                return None
            return self._clean(df, symbol, "Ticker")
        except Exception as e:
            print(f"[DATA] Ticker failed {symbol}: {e}")
            return None

    def _try_download(self, symbol, interval, period):
        min_bars = _MIN_BARS.get(interval, 50)
        for attempt in range(3):
            try:
                df = yf.download(symbol, period=period, interval=interval,
                                 progress=False, auto_adjust=True, timeout=20)
                result = self._clean(df, symbol, "download")
                if result is not None and len(result) >= min_bars:
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

    @staticmethod
    def _cap_bars(df: pd.DataFrame, interval: str) -> pd.DataFrame:
        """Limit bars to prevent slow chart rendering."""
        cap = _MAX_BARS.get(interval, 1000)
        if len(df) > cap:
            print(f"[DATA] Capping {len(df)} bars → {cap} for interval={interval}")
            return df.iloc[-cap:].copy()
        return df