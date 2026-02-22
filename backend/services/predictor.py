from typing import List
import pandas as pd

from backend.interfaces         import IPredictor
from backend.interfaces.news_source  import NewsArticle
from backend.interfaces.predictor    import Prediction
from backend.indicators import EMA, RSI, ATR, Supertrend, BollingerBands, MACD


class TechnicalNewsPredictor(IPredictor):
    def predict(self, df: pd.DataFrame, news: List[NewsArticle], symbol: str, interval: str) -> Prediction:
        v = self._compute_values(df)
        tech_score, bull_reasons, bear_reasons = self._score_technical(v, df["Close"].iloc[-1])
        news_score, news_delta = self._score_news(news)

        if news_delta > 15:   bull_reasons.append(f"News sentiment strongly positive ({len(news)} articles)")
        elif news_delta > 5:  bull_reasons.append("News sentiment mildly positive")
        elif news_delta < -15:bear_reasons.append(f"News sentiment strongly negative ({len(news)} articles)")
        elif news_delta < -5: bear_reasons.append("News sentiment mildly negative")

        final     = max(5, min(95, tech_score * 0.70 + news_score * 0.30))
        direction = "BULLISH" if final >= 60 else ("BEARISH" if final <= 40 else "NEUTRAL")
        cur       = float(df["Close"].iloc[-1])
        atr       = v["atr"]

        tp1 = round(cur + atr,       2) if direction == "BULLISH" else round(cur - atr,       2)
        tp2 = round(cur + atr * 2.5, 2) if direction == "BULLISH" else round(cur - atr * 2.5, 2)
        sl  = round(cur - atr,       2) if direction == "BULLISH" else (round(cur + atr, 2) if direction == "BEARISH" else None)

        return Prediction(
            symbol       = symbol,
            direction    = direction,
            confidence   = round(final, 1),
            tech_score   = round(tech_score, 1),
            news_score   = round(news_score, 1),
            bull_reasons = bull_reasons,
            bear_reasons = bear_reasons,
            current      = round(cur, 4),
            tp1          = tp1,
            tp2          = tp2,
            sl           = sl,
            atr          = round(atr, 4),
            rsi          = round(v["rsi"], 2),
            interval     = interval,
        )

    def _compute_values(self, df):
        vol  = df["Volume"] if "Volume" in df.columns else pd.Series(1, index=df.index)
        e9   = EMA(9).compute(df)
        e21  = EMA(21).compute(df)
        e50  = EMA(50).compute(df)
        e200 = EMA(200).compute(df)
        r    = RSI(14).compute(df)
        a    = ATR(14).compute(df)
        st   = Supertrend(3, 10).compute(df)
        macd = MACD(12, 26, 9).compute(df)
        bb   = BollingerBands(20, 2).compute(df)
        c    = df["Close"]
        return {
            "rsi":    float(r.iloc[-1]),
            "e9":     float(e9.iloc[-1]),
            "e21":    float(e21.iloc[-1]),
            "e50":    float(e50.iloc[-1]),
            "e200":   float(e200.iloc[-1]),
            "st":     float(st.iloc[-1]),
            "macd":   float(macd["macd"].iloc[-1]),
            "msig":   float(macd["signal"].iloc[-1]),
            "atr":    float(a.iloc[-20:].mean()),
            "vol":    float(vol.iloc[-1]),
            "vol_ma": float(vol.rolling(20).mean().iloc[-1]),
            "bb_up":  float(bb["upper"].iloc[-1]),
            "bb_lo":  float(bb["lower"].iloc[-1]),
            "chg_5":  float((c.iloc[-1] / c.iloc[-6] - 1) * 100) if len(c) > 5 else 0,
        }

    @staticmethod
    def _score_technical(v, cur):
        score = 50
        bull  = []
        bear  = []

        if v["e9"] > v["e21"] > v["e50"]:
            score += 14; bull.append("EMA 9 > 21 > 50 — strong uptrend alignment")
        elif v["e9"] < v["e21"] < v["e50"]:
            score -= 14; bear.append("EMA 9 < 21 < 50 — strong downtrend alignment")
        elif v["e9"] > v["e21"]:
            score += 7;  bull.append("EMA 9 above EMA 21 — short-term bullish")
        else:
            score -= 7;  bear.append("EMA 9 below EMA 21 — short-term bearish")

        if cur > v["e200"]: score += 10; bull.append("Price above EMA 200 — long-term uptrend")
        else:               score -= 10; bear.append("Price below EMA 200 — long-term downtrend")

        if v["rsi"] > 65:   score += 10; bull.append(f"RSI {v['rsi']:.0f} — strong bullish momentum")
        elif v["rsi"] > 55: score += 5;  bull.append(f"RSI {v['rsi']:.0f} — moderate bullish momentum")
        elif v["rsi"] < 35: score -= 10; bear.append(f"RSI {v['rsi']:.0f} — oversold / bearish")
        elif v["rsi"] < 45: score -= 5;  bear.append(f"RSI {v['rsi']:.0f} — moderate bearish momentum")

        if v["st"] < 0:  score += 10; bull.append("Supertrend bullish — price above support")
        else:            score -= 10; bear.append("Supertrend bearish — price below resistance")

        if v["macd"] > v["msig"]: score += 8; bull.append("MACD above Signal — bullish crossover")
        else:                      score -= 8; bear.append("MACD below Signal — bearish crossover")

        bb_range = max(0.01, v["bb_up"] - v["bb_lo"])
        bb_pct   = (cur - v["bb_lo"]) / bb_range
        if bb_pct > 0.8:   bull.append("Price in upper BB zone — strong momentum")
        elif bb_pct < 0.2: bear.append("Price in lower BB zone — selling pressure")

        if v["chg_5"] > 1.5:    score += 5;  bull.append(f"5-bar momentum +{v['chg_5']:.1f}%")
        elif v["chg_5"] < -1.5: score -= 5;  bear.append(f"5-bar momentum {v['chg_5']:.1f}%")

        if v["vol"] > v["vol_ma"] * 1.4:
            lbl = "Volume spike confirms bullish move" if score > 50 else "Volume spike on bearish move"
            (bull if score > 50 else bear).append(lbl)

        return max(5, min(95, score)), bull, bear

    @staticmethod
    def _score_news(news):
        if not news:
            return 50, 0
        delta = sum(a.score - 50 for a in news[:10]) / min(10, len(news))
        return max(5, min(95, 50 + delta)), delta
