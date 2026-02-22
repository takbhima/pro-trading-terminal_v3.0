"""
Indicators package — each indicator is a self-contained class implementing IIndicator.
"""
import numpy as np
import pandas as pd

from backend.interfaces import IIndicator


class EMA(IIndicator):
    def __init__(self, length: int):
        self._length = length

    @property
    def name(self) -> str:
        return f"EMA_{self._length}"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        return df["Close"].ewm(span=self._length, adjust=False).mean()


class RSI(IIndicator):
    def __init__(self, length: int = 14):
        self._length = length

    @property
    def name(self) -> str:
        return f"RSI_{self._length}"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        delta    = df["Close"].diff()
        gain     = delta.clip(lower=0)
        loss     = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=self._length - 1, adjust=False).mean()
        avg_loss = loss.ewm(com=self._length - 1, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        return 100 - (100 / (1 + rs))


class ATR(IIndicator):
    def __init__(self, length: int = 14):
        self._length = length

    @property
    def name(self) -> str:
        return f"ATR_{self._length}"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        prev_close = df["Close"].shift(1)
        tr = pd.concat([
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"]  - prev_close).abs(),
        ], axis=1).max(axis=1)
        return tr.ewm(com=self._length - 1, adjust=False).mean()


class Supertrend(IIndicator):
    def __init__(self, factor: float = 3.0, atr_len: int = 10):
        self._factor  = factor
        self._atr_len = atr_len

    @property
    def name(self) -> str:
        return f"Supertrend_{self._factor}_{self._atr_len}"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        atr_vals  = ATR(self._atr_len).compute(df)
        hl2       = (df["High"] + df["Low"]) / 2.0
        raw_upper = hl2 + self._factor * atr_vals
        raw_lower = hl2 - self._factor * atr_vals

        n         = len(df)
        upper     = np.zeros(n)
        lower     = np.zeros(n)
        st_dir    = np.zeros(n)
        close_arr = df["Close"].values
        upper_arr = raw_upper.values
        lower_arr = raw_lower.values

        upper[0]  = upper_arr[0]
        lower[0]  = lower_arr[0]
        st_dir[0] = 1

        for i in range(1, n):
            lower[i] = lower_arr[i] if (lower_arr[i] > lower[i-1] or close_arr[i-1] < lower[i-1]) else lower[i-1]
            upper[i] = upper_arr[i] if (upper_arr[i] < upper[i-1] or close_arr[i-1] > upper[i-1]) else upper[i-1]
            if st_dir[i-1] == 1:
                st_dir[i] = -1 if close_arr[i] > upper[i] else 1
            else:
                st_dir[i] = 1 if close_arr[i] < lower[i] else -1

        return pd.Series(st_dir, index=df.index, dtype=float)


class VWAP(IIndicator):
    @property
    def name(self) -> str:
        return "VWAP"

    def compute(self, df: pd.DataFrame) -> pd.Series:
        tp  = (df["High"] + df["Low"] + df["Close"]) / 3
        vol = df["Volume"].replace(0, np.nan)
        return (tp * vol).cumsum() / vol.cumsum()


class BollingerBands(IIndicator):
    def __init__(self, length: int = 20, std_dev: float = 2.0):
        self._length  = length
        self._std_dev = std_dev

    @property
    def name(self) -> str:
        return f"BB_{self._length}_{self._std_dev}"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        mid = df["Close"].rolling(self._length).mean()
        std = df["Close"].rolling(self._length).std()
        return pd.DataFrame({
            "mid":   mid,
            "upper": mid + self._std_dev * std,
            "lower": mid - self._std_dev * std,
        }, index=df.index)


class MACD(IIndicator):
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self._fast   = fast
        self._slow   = slow
        self._signal = signal

    @property
    def name(self) -> str:
        return f"MACD_{self._fast}_{self._slow}_{self._signal}"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        c    = df["Close"]
        macd = c.ewm(span=self._fast, adjust=False).mean() - c.ewm(span=self._slow, adjust=False).mean()
        sig  = macd.ewm(span=self._signal, adjust=False).mean()
        return pd.DataFrame({
            "macd":      macd,
            "signal":    sig,
            "histogram": macd - sig,
        }, index=df.index)


def crossover(s1: pd.Series, s2: pd.Series) -> pd.Series:
    return (s1.shift(1) <= s2.shift(1)) & (s1 > s2)


def crossunder(s1: pd.Series, s2: pd.Series) -> pd.Series:
    return (s1.shift(1) >= s2.shift(1)) & (s1 < s2)
