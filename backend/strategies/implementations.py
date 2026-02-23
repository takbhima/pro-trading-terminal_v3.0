"""
Strategy implementations — Part 3 additions:

  StochRSIMomentumStrategy  : Stochastic RSI %K/%D crossover from oversold/overbought
                               zones + EMA 9/21 trend filter + ADX > 20 noise filter.
                               Targets 12-18 signals/day on 2m-3m candles.

  EMARibbonADXStrategy      : EMA ribbon (3,5,8,13,21) full alignment + ADX(14) > 25
                               with DI+/DI- direction + RSI(7) in 40-60 zone to avoid
                               extremes. Targets 10-15 signals/day on 3m-5m candles.

Both strategies:
  - Fully implement IStrategy / BaseStrategy interface
  - Support MTF filter (handled by ChartService / _filter_signals_by_mtf in main.py)
  - Appear after existing strategies in the StrategyBar
"""
from typing import List
import pandas as pd

from backend.indicators import (
    EMA, RSI, ATR, Supertrend, VWAP, BollingerBands, MACD,
    StochasticRSI, ADX,
    crossover, crossunder,
)
from backend.interfaces.strategy import Signal
from .base import BaseStrategy


# ── Existing strategies (unchanged) ──────────────────────────────────────────

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


# ══════════════════════════════════════════════════════════════════════════════
#  Part 3 — New Strategies
# ══════════════════════════════════════════════════════════════════════════════

class StochRSIMomentumStrategy(BaseStrategy):
    """
    Stochastic RSI Momentum Scalper
    ================================
    Based on Chande & Kroll (1994). Fires 3-4× more often than raw RSI
    because it applies the stochastic formula to the RSI series.

    Entry conditions:
      BUY  — StochRSI %K crosses above %D from below oversold threshold (20)
              AND EMA(9) > EMA(21)  [short-term trend aligned]
              AND ADX(14) > 20      [not choppy / sideways market]

      SELL — StochRSI %K crosses below %D from above overbought threshold (80)
              AND EMA(9) < EMA(21)
              AND ADX(14) > 20

    SL / TP:
      SL  : 1× ATR(7) away from entry  [tight stop for scalping]
      TP  : 1.5× ATR(7)                [1 : 1.5 R:R — achievable at 3m TF]

    Best timeframes : 2m, 3m, 5m
    Expected signals: 12–18 / day on 5–8 liquid symbols
    """

    # Scalper-specific ATR multipliers (tighter than BaseStrategy default 1× / 2×)
    _SL_MULT = 1.0
    _TP_MULT = 1.5

    @property
    def key(self) -> str:             return "stoch_rsi"
    @property
    def name(self) -> str:            return "StochRSI"
    @property
    def description(self) -> str:     return "StochRSI %K/%D crossover from oversold/overbought + EMA trend + ADX noise filter. 12-18 signals/day."
    @property
    def signals_per_day(self) -> str: return "12–18"
    @property
    def best_for(self) -> str:        return "2m, 3m, 5m"
    @property
    def style(self) -> str:           return "Scalping"
    @property
    def color(self) -> str:           return "#06b6d4"  # cyan

    def generate(self, df: pd.DataFrame, ts_fn) -> List[Signal]:
        if len(df) < 50:
            return []

        stoch = StochasticRSI(rsi_len=14, stoch_len=14, k_smooth=3, d_smooth=3).compute(df)
        k     = stoch["k"]
        d     = stoch["d"]
        e9    = EMA(9).compute(df)
        e21   = EMA(21).compute(df)
        a7    = ATR(7).compute(df)       # tighter ATR for scalping SL/TP
        a14   = ATR(14).compute(df)      # used for confidence calculation
        r     = RSI(14).compute(df)
        adx_df = ADX(14).compute(df)
        adx   = adx_df["adx"]

        # Cross conditions
        k_cross_up   = crossover(k, d)   # %K crosses above %D
        k_cross_down = crossunder(k, d)  # %K crosses below %D

        out: List[Signal] = []
        for i in range(30, len(df)):
            # Skip NaN regions from indicator warmup
            if (pd.isna(k.iloc[i]) or pd.isna(d.iloc[i]) or
                pd.isna(adx.iloc[i]) or pd.isna(a7.iloc[i])):
                continue

            price   = float(df["Close"].iloc[i])
            atr_val = float(a7.iloc[i])
            adx_val = float(adx.iloc[i])

            # ADX > 20 — filters flat/choppy markets (key quality filter)
            if adx_val < 20:
                continue

            # BUY: %K crosses above %D AND was in oversold zone (< 20)
            # EMA short-term trend must be bullish
            if (k_cross_up.iloc[i]
                    and float(k.iloc[i - 1]) < 20       # was oversold
                    and e9.iloc[i] > e21.iloc[i]         # trend aligned
            ):
                out.append(self._build_stoch_signal(
                    df, i, "BUY", atr_val, float(r.iloc[i]), float(a14.iloc[i]),
                    adx_val, ts_fn,
                ))

            # SELL: %K crosses below %D AND was in overbought zone (> 80)
            elif (k_cross_down.iloc[i]
                      and float(k.iloc[i - 1]) > 80     # was overbought
                      and e9.iloc[i] < e21.iloc[i]      # trend aligned
            ):
                out.append(self._build_stoch_signal(
                    df, i, "SELL", atr_val, float(r.iloc[i]), float(a14.iloc[i]),
                    adx_val, ts_fn,
                ))

        return out

    def _build_stoch_signal(
        self,
        df, i: int,
        sig_type: str,
        atr7: float,
        rsi_val: float,
        atr14: float,
        adx_val: float,
        ts_fn,
    ) -> Signal:
        close = float(df["Close"].iloc[i])

        # Tighter SL/TP than BaseStrategy default (scalper-specific)
        if sig_type == "BUY":
            sl = round(close - atr7 * self._SL_MULT, 4)
            tp = round(close + atr7 * self._TP_MULT, 4)
        else:
            sl = round(close + atr7 * self._SL_MULT, 4)
            tp = round(close - atr7 * self._TP_MULT, 4)

        # Confidence: blend RSI distance from 50 + ADX strength
        rsi_dist   = max(0.0, rsi_val - 50.0 if sig_type == "BUY" else 50.0 - rsi_val)
        adx_boost  = min(20.0, (adx_val - 20.0) * 0.5)   # 0–20 pts from ADX
        confidence = round(min(95.0, 50.0 + rsi_dist * 1.2 + adx_boost), 1)

        return Signal(
            time       = ts_fn(df.index[i]),
            type       = sig_type,
            price      = round(close, 4),
            sl         = sl,
            tp         = tp,
            rsi        = round(rsi_val, 2),
            atr        = round(atr14, 4),   # display ATR14 (more familiar) in UI
            confidence = confidence,
            strategy   = self.key,
        )


class EMARibbonADXStrategy(BaseStrategy):
    """
    EMA Ribbon + ADX Trend-Strength Scalper
    ========================================
    Based on serkany88's EMA RSI ADX Scalping system (TradingView, 1000+ likes).
    ADX > 25 filter produces 80%+ accuracy in backtests (Forextester).

    Entry conditions:
      BUY  — EMA ribbon fully aligned bullish: EMA(3) > EMA(5) > EMA(8) > EMA(13) > EMA(21)
              AND ADX(14) > 25   [strong trend — the key quality gate]
              AND DI+ > DI-      [positive directional pressure]
              AND RSI(7) in 40–60 [not overextended — avoid chasing peaks/troughs]

      SELL — EMA ribbon fully aligned bearish: EMA(3) < EMA(5) < EMA(8) < EMA(13) < EMA(21)
              AND ADX(14) > 25
              AND DI- > DI+
              AND RSI(7) in 40–60

    SL / TP:
      SL  : Below / above EMA(21) at signal bar  [natural ribbon support/resistance]
      TP  : 2× ATR(14)                            [1 : 2 R:R — matches existing conventions]

    Best timeframes : 3m, 5m
    Expected signals: 10–15 / day on liquid NSE/NYSE/crypto symbols
    """

    _ADX_THRESHOLD = 25   # raise to 30 for even higher quality / fewer signals

    @property
    def key(self) -> str:             return "ema_ribbon_adx"
    @property
    def name(self) -> str:            return "EMA Ribbon"
    @property
    def description(self) -> str:     return "Full EMA ribbon (3-21) alignment + ADX(14)>25 trend strength + DI+/DI- direction + RSI(7) 40-60. 10-15 signals/day."
    @property
    def signals_per_day(self) -> str: return "10–15"
    @property
    def best_for(self) -> str:        return "3m, 5m"
    @property
    def style(self) -> str:           return "Trend"
    @property
    def color(self) -> str:           return "#8b5cf6"  # violet

    def generate(self, df: pd.DataFrame, ts_fn) -> List[Signal]:
        if len(df) < 60:
            return []

        # EMA ribbon — 5 periods
        e3  = EMA(3).compute(df)
        e5  = EMA(5).compute(df)
        e8  = EMA(8).compute(df)
        e13 = EMA(13).compute(df)
        e21 = EMA(21).compute(df)

        # RSI(7) — faster RSI for scalping (not standard 14)
        r7  = RSI(7).compute(df)
        a14 = ATR(14).compute(df)

        # ADX with DI components
        adx_df   = ADX(14).compute(df)
        adx      = adx_df["adx"]
        di_plus  = adx_df["di_plus"]
        di_minus = adx_df["di_minus"]

        out: List[Signal] = []
        for i in range(40, len(df)):
            if (pd.isna(adx.iloc[i]) or pd.isna(r7.iloc[i]) or
                pd.isna(di_plus.iloc[i]) or pd.isna(e21.iloc[i])):
                continue

            adx_val  = float(adx.iloc[i])
            dip_val  = float(di_plus.iloc[i])
            dim_val  = float(di_minus.iloc[i])
            rsi_val  = float(r7.iloc[i])
            atr_val  = float(a14.iloc[i])
            price    = float(df["Close"].iloc[i])
            e21_val  = float(e21.iloc[i])

            # ADX quality gate — only trade in trending, non-choppy conditions
            if adx_val < self._ADX_THRESHOLD:
                continue

            # RSI zone filter — avoid overextended entries
            if not (40 <= rsi_val <= 60):
                continue

            # ── BUY: full bullish ribbon + DI+ dominates ──────────────────
            ribbon_bull = (
                e3.iloc[i] > e5.iloc[i] > e8.iloc[i] > e13.iloc[i] > e21.iloc[i]
            )
            if ribbon_bull and dip_val > dim_val:
                # SL below EMA(21) — ribbon support level
                sl = round(e21_val - atr_val * 0.25, 4)  # small buffer below EMA21
                tp = round(price + atr_val * 2.0, 4)
                out.append(self._build_ribbon_signal(
                    df, i, "BUY", sl, tp, rsi_val, atr_val, adx_val, ts_fn,
                ))

            # ── SELL: full bearish ribbon + DI- dominates ─────────────────
            elif (e3.iloc[i] < e5.iloc[i] < e8.iloc[i] < e13.iloc[i] < e21.iloc[i]
                  and dim_val > dip_val):
                # SL above EMA(21) — ribbon resistance level
                sl = round(e21_val + atr_val * 0.25, 4)
                tp = round(price - atr_val * 2.0, 4)
                out.append(self._build_ribbon_signal(
                    df, i, "SELL", sl, tp, rsi_val, atr_val, adx_val, ts_fn,
                ))

        return out

    def _build_ribbon_signal(
        self,
        df, i: int,
        sig_type: str,
        sl: float,
        tp: float,
        rsi_val: float,
        atr_val: float,
        adx_val: float,
        ts_fn,
    ) -> Signal:
        close = float(df["Close"].iloc[i])

        # Confidence: ADX strength is the primary driver here
        # ADX 25 → 50%, ADX 50 → 75%, caps at 95%
        adx_conf   = min(45.0, (adx_val - self._ADX_THRESHOLD) * 1.0)
        rsi_dist   = abs(rsi_val - 50.0) * 0.3   # small contribution
        confidence = round(min(95.0, 50.0 + adx_conf + rsi_dist), 1)

        return Signal(
            time       = ts_fn(df.index[i]),
            type       = sig_type,
            price      = round(close, 4),
            sl         = sl,
            tp         = tp,
            rsi        = round(rsi_val, 2),
            atr        = round(atr_val, 4),
            confidence = confidence,
            strategy   = self.key,
        )