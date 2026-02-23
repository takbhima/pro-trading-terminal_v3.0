"""
Indicators package — each indicator is a self-contained class implementing IIndicator.

Part 3 additions:
  - StochasticRSI  : Chande & Kroll (1994) — %K and %D lines from RSI series
  - ADX            : Average Directional Index with DI+ and DI- components
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


# ══════════════════════════════════════════════════════════════════════════════
#  Part 3 — New Indicators
# ══════════════════════════════════════════════════════════════════════════════

class StochasticRSI(IIndicator):
    """
    Stochastic RSI — Chande & Kroll (1994).

    Applies the Stochastic oscillator formula to the RSI series rather than
    price, making it 3-4× more sensitive than raw RSI.  Returns a DataFrame
    with two columns:
        k  — raw StochRSI (fast line), range 0–100
        d  — smoothed %D (signal line), EMA of k

    Usage:
        stoch = StochasticRSI(rsi_len=14, stoch_len=14, k_smooth=3, d_smooth=3)
        df_stoch = stoch.compute(df)   # → DataFrame with 'k' and 'd' columns

    Signal logic used by EMA Scalper:
        BUY  when k crosses above d from below 20 (oversold exit)
        SELL when k crosses below d from above 80 (overbought exit)
    """

    def __init__(
        self,
        rsi_len:   int = 14,
        stoch_len: int = 14,
        k_smooth:  int = 3,
        d_smooth:  int = 3,
    ):
        self._rsi_len   = rsi_len
        self._stoch_len = stoch_len
        self._k_smooth  = k_smooth
        self._d_smooth  = d_smooth

    @property
    def name(self) -> str:
        return f"StochRSI_{self._rsi_len}_{self._stoch_len}"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        # Step 1 — RSI series
        rsi = RSI(self._rsi_len).compute(df)

        # Step 2 — Stochastic of RSI: (RSI - lowest_RSI) / (highest_RSI - lowest_RSI)
        rsi_min = rsi.rolling(self._stoch_len).min()
        rsi_max = rsi.rolling(self._stoch_len).max()
        rsi_range = (rsi_max - rsi_min).replace(0, np.nan)
        k_raw = ((rsi - rsi_min) / rsi_range * 100).fillna(50)

        # Step 3 — Smooth %K, then derive %D as EMA of %K
        k = k_raw.ewm(span=self._k_smooth, adjust=False).mean()
        d = k.ewm(span=self._d_smooth, adjust=False).mean()

        return pd.DataFrame({"k": k, "d": d}, index=df.index)


class ADX(IIndicator):
    """
    Average Directional Index (J. Welles Wilder, 1978).

    Returns a DataFrame with three columns:
        adx  — trend strength (0–100); values > 25 indicate strong trend
        di_plus  — positive directional indicator (DI+)
        di_minus — negative directional indicator (DI-)

    Usage:
        adx_df = ADX(length=14).compute(df)

    Signal logic:
        Strong uptrend  : adx > 25 AND di_plus > di_minus
        Strong downtrend: adx > 25 AND di_minus > di_plus
    """

    def __init__(self, length: int = 14):
        self._length = length

    @property
    def name(self) -> str:
        return f"ADX_{self._length}"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        high  = df["High"].values
        low   = df["Low"].values
        close = df["Close"].values
        n     = len(df)

        # True range (same formula as ATR class but we need it raw here)
        tr     = np.zeros(n)
        dm_pos = np.zeros(n)
        dm_neg = np.zeros(n)

        for i in range(1, n):
            hl   = high[i]  - low[i]
            hc   = abs(high[i]  - close[i - 1])
            lc   = abs(low[i]   - close[i - 1])
            tr[i] = max(hl, hc, lc)

            up_move   = high[i]  - high[i - 1]
            down_move = low[i - 1] - low[i]

            dm_pos[i] = up_move   if (up_move   > down_move and up_move   > 0) else 0
            dm_neg[i] = down_move if (down_move > up_move   and down_move > 0) else 0

        # Wilder smoothing (same as Wilder's EMA: multiplier = 1/length)
        alpha = 1.0 / self._length
        atr_w    = np.zeros(n)
        dmp_w    = np.zeros(n)
        dmn_w    = np.zeros(n)

        # Seed with sum of first `length` values (Wilder's initialisation)
        seed = self._length
        if n <= seed:
            # Not enough data — return NaN frame
            nan_series = pd.Series(np.nan, index=df.index)
            return pd.DataFrame({"adx": nan_series, "di_plus": nan_series, "di_minus": nan_series})

        atr_w[seed]  = tr[1:seed + 1].sum()
        dmp_w[seed]  = dm_pos[1:seed + 1].sum()
        dmn_w[seed]  = dm_neg[1:seed + 1].sum()

        for i in range(seed + 1, n):
            atr_w[i] = atr_w[i - 1] - (atr_w[i - 1] / self._length) + tr[i]
            dmp_w[i] = dmp_w[i - 1] - (dmp_w[i - 1] / self._length) + dm_pos[i]
            dmn_w[i] = dmn_w[i - 1] - (dmn_w[i - 1] / self._length) + dm_neg[i]

        # DI+ and DI-
        with np.errstate(divide="ignore", invalid="ignore"):
            di_plus  = np.where(atr_w > 0, dmp_w / atr_w * 100, 0.0)
            di_minus = np.where(atr_w > 0, dmn_w / atr_w * 100, 0.0)

        # DX and ADX
        di_sum  = di_plus + di_minus
        with np.errstate(divide="ignore", invalid="ignore"):
            dx = np.where(di_sum > 0, np.abs(di_plus - di_minus) / di_sum * 100, 0.0)

        adx = np.zeros(n)
        # Seed ADX with average of first `length` DX values after seed
        adx_seed_start = seed + 1
        adx_seed_end   = adx_seed_start + self._length
        if adx_seed_end <= n:
            adx[adx_seed_end - 1] = dx[adx_seed_start:adx_seed_end].mean()
            for i in range(adx_seed_end, n):
                adx[i] = (adx[i - 1] * (self._length - 1) + dx[i]) / self._length

        # Zero-out the seeding region (not enough data)
        adx[:adx_seed_end - 1]  = np.nan
        di_plus[:seed]          = np.nan
        di_minus[:seed]         = np.nan

        return pd.DataFrame({
            "adx":      adx,
            "di_plus":  di_plus,
            "di_minus": di_minus,
        }, index=df.index)


# ── Helpers ───────────────────────────────────────────────────────────────────

def crossover(s1: pd.Series, s2: pd.Series) -> pd.Series:
    return (s1.shift(1) <= s2.shift(1)) & (s1 > s2)


def crossunder(s1: pd.Series, s2: pd.Series) -> pd.Series:
    return (s1.shift(1) >= s2.shift(1)) & (s1 < s2)
