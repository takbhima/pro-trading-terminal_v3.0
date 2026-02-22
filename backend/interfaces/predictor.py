from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd

from .news_source import NewsArticle


@dataclass(frozen=True)
class Prediction:
    symbol:       str
    direction:    str
    confidence:   float
    tech_score:   float
    news_score:   float
    bull_reasons: List[str]       = field(default_factory=list)
    bear_reasons: List[str]       = field(default_factory=list)
    current:      float           = 0.0
    tp1:          float           = 0.0
    tp2:          float           = 0.0
    sl:           Optional[float] = None
    atr:          float           = 0.0
    rsi:          float           = 0.0
    interval:     str             = '1d'


class IPredictor(ABC):
    @abstractmethod
    def predict(self, df: pd.DataFrame, news: List[NewsArticle], symbol: str, interval: str) -> Prediction: ...
