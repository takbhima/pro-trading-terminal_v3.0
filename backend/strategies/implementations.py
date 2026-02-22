from typing import List
import pandas as pd

from backend.indicators import (
    EMA, RSI, ATR, Supertrend, VWAP, BollingerBands, MACD,
    crossover, crossunder,
)
from backend.interfaces.strategy import Signal
from .base import BaseStrategy


class ProMTFStrategy(BaseStrategy):
    @property
    def key(self) -> str:             return "pro_mtf"
    @property
    def name(self) -> str:            return "Pro MTF"
    @property
    def description(self) -> str:     return "EMA 9/21 cross + RSI + EMA 200 trend + Supertrend. Best for swing trading."
    @property
    def signals_per_day(self) -> str: return "1–3"
    @property
    def best_for(self) -> str:        return "1D, 1W"
    @property
    def style(self) -> str:           return "Swing"
    @property
    def color(self) -> str:           return "#3b82f6"

    def generate(self, df: pd.DataFrame, ts_fn) -> List[Signal]:
        e9   = EMA(9).compute(df)
        e21  = EMA(21).compute(df)
        e200 = EMA(200).compute(df)
        r    = RSI(14).compute(df)
        a    = ATR(14).compute(df)
        st   = Supertrend(3, 10).compute(df)
        cu   = crossover(e9, e21)
        cd   = crossunder(e9, e21)
        out: List[Signal] = []
        for i in range(1, len(df)):
            price = float(df["Close"].iloc[i])
            if cu.iloc[i] and r.iloc[i] > 50 and price > e200.iloc[i] and st.iloc[i] < 0:
                out.append(self._build_signal(df, i, "BUY", a, r, ts_fn))
            elif cd.iloc[i] and r.iloc[i] < 50 and price < e200.iloc[i] and st.iloc[i] > 0:
                out.append(self._build_signal(df, i, "SELL", a, r, ts_fn))
        return out


class VWAPEMAStrategy(BaseStrategy):
    @property
    def key(self) -> str:             return "vwap_ema"
    @property
    def name(self) -> str:            return "VWAP + EMA"
    @property
    def description(self) -> str:     return "Price vs VWAP crossover + EMA 9/21 direction + RSI. Classic intraday."
    @property
    def signals_per_day(self) -> str: return "4–6"
    @property
    def best_for(self) -> str:        return "5m, 15m"
    @property
    def style(self) -> str:           return "Intraday"
    @property
    def color(self) -> str:           return "#00d084"

    def generate(self, df: pd.DataFrame, ts_fn) -> List[Signal]:
        vwap  = VWAP().compute(df)
        e9    = EMA(9).compute(df)
        e21   = EMA(21).compute(df)
        r     = RSI(14).compute(df)
        a     = ATR(14).compute(df)
        cv_up = crossover(df["Close"], vwap)
        cv_dn = crossunder(df["Close"], vwap)
        out: List[Signal] = []
        for i in range(1, len(df)):
            if cv_up.iloc[i] and e9.iloc[i] > e21.iloc[i] and r.iloc[i] > 50:
                out.append(self._build_signal(df, i, "BUY", a, r, ts_fn))
            elif cv_dn.iloc[i] and e9.iloc[i] < e21.iloc[i] and r.iloc[i] < 50:
                out.append(self._build_signal(df, i, "SELL", a, r, ts_fn))
        return out


class RSIReversalStrategy(BaseStrategy):
    @property
    def key(self) -> str:             return "rsi_reversal"
    @property
    def name(self) -> str:            return "RSI Reversal"
    @property
    def description(self) -> str:     return "RSI exits oversold (<30) or overbought (>70) zones with EMA 50 filter."
    @property
    def signals_per_day(self) -> str: return "3–6"
    @property
    def best_for(self) -> str:        return "5m, 15m"
    @property
    def style(self) -> str:           return "Mean Reversion"
    @property
    def color(self) -> str:           return "#a78bfa"

    def generate(self, df: pd.DataFrame, ts_fn) -> List[Signal]:
        r   = RSI(14).compute(df)
        a   = ATR(14).compute(df)
        e50 = EMA(50).compute(df)
        rp  = r.shift(1).fillna(50)
        cross30_up   = (rp < 30) & (r >= 30)
        cross70_down = (rp > 70) & (r <= 70)
        out: List[Signal] = []
        for i in range(1, len(df)):
            price = float(df["Close"].iloc[i])
            if cross30_up.iloc[i] and price > e50.iloc[i]:
                out.append(self._build_signal(df, i, "BUY", a, r, ts_fn))
            elif cross70_down.iloc[i] and price < e50.iloc[i]:
                out.append(self._build_signal(df, i, "SELL", a, r, ts_fn))
        return out


class BollingerBreakoutStrategy(BaseStrategy):
    @property
    def key(self) -> str:             return "bollinger"
    @property
    def name(self) -> str:            return "Bollinger Breakout"
    @property
    def description(self) -> str:     return "Price breaks Bollinger Band + RSI momentum + volume spike confirmation."
    @property
    def signals_per_day(self) -> str: return "4–6"
    @property
    def best_for(self) -> str:        return "5m, 15m"
    @property
    def style(self) -> str:           return "Breakout"
    @property
    def color(self) -> str:           return "#f0b429"

    def generate(self, df: pd.DataFrame, ts_fn) -> List[Signal]:
        bb   = BollingerBands(20, 2).compute(df)
        r    = RSI(14).compute(df)
        a    = ATR(14).compute(df)
        vm   = df["Volume"].rolling(20).mean()
        c_p  = df["Close"].shift(1)
        out: List[Signal] = []
        for i in range(20, len(df)):
            price  = float(df["Close"].iloc[i])
            vol_ok = float(df["Volume"].iloc[i]) > float(vm.iloc[i]) * 1.3
            if float(c_p.iloc[i]) <= float(bb["upper"].iloc[i-1]) and price > float(bb["upper"].iloc[i]) and r.iloc[i] > 55 and vol_ok:
                out.append(self._build_signal(df, i, "BUY", a, r, ts_fn))
            elif float(c_p.iloc[i]) >= float(bb["lower"].iloc[i-1]) and price < float(bb["lower"].iloc[i]) and r.iloc[i] < 45 and vol_ok:
                out.append(self._build_signal(df, i, "SELL", a, r, ts_fn))
        return out


class MACDCrossoverStrategy(BaseStrategy):
    @property
    def key(self) -> str:             return "macd"
    @property
    def name(self) -> str:            return "MACD Crossover"
    @property
    def description(self) -> str:     return "MACD crosses Signal line + histogram confirms + RSI filter."
    @property
    def signals_per_day(self) -> str: return "4–6"
    @property
    def best_for(self) -> str:        return "15m, 1H"
    @property
    def style(self) -> str:           return "Trend"
    @property
    def color(self) -> str:           return "#fb7185"

    def generate(self, df: pd.DataFrame, ts_fn) -> List[Signal]:
        macd_df = MACD(12, 26, 9).compute(df)
        r       = RSI(14).compute(df)
        a       = ATR(14).compute(df)
        cu_m    = crossover(macd_df["macd"],  macd_df["signal"])
        cd_m    = crossunder(macd_df["macd"], macd_df["signal"])
        out: List[Signal] = []
        for i in range(1, len(df)):
            if cu_m.iloc[i] and macd_df["histogram"].iloc[i] > 0 and r.iloc[i] > 50:
                out.append(self._build_signal(df, i, "BUY", a, r, ts_fn))
            elif cd_m.iloc[i] and macd_df["histogram"].iloc[i] < 0 and r.iloc[i] < 50:
                out.append(self._build_signal(df, i, "SELL", a, r, ts_fn))
        return out


class SupertrendScalperStrategy(BaseStrategy):
    @property
    def key(self) -> str:             return "supertrend_scalper"
    @property
    def name(self) -> str:            return "ST Scalper"
    @property
    def description(self) -> str:     return "Fast Supertrend(2,7) direction flip + RSI confirmation. Most signals."
    @property
    def signals_per_day(self) -> str: return "6–12"
    @property
    def best_for(self) -> str:        return "5m"
    @property
    def style(self) -> str:           return "Scalping"
    @property
    def color(self) -> str:           return "#f97316"

    def generate(self, df: pd.DataFrame, ts_fn) -> List[Signal]:
        st_f = Supertrend(2.0, 7).compute(df)
        r    = RSI(14).compute(df)
        a    = ATR(14).compute(df)
        st_p = st_f.shift(1)
        out: List[Signal] = []
        for i in range(1, len(df)):
            if st_p.iloc[i] > 0 and st_f.iloc[i] < 0 and r.iloc[i] > 45:
                out.append(self._build_signal(df, i, "BUY", a, r, ts_fn))
            elif st_p.iloc[i] < 0 and st_f.iloc[i] > 0 and r.iloc[i] < 55:
                out.append(self._build_signal(df, i, "SELL", a, r, ts_fn))
        return out
