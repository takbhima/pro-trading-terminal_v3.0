from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional
import pandas as pd


@dataclass(frozen=True)
class Signal:
    time:       int
    type:       str        # 'BUY' | 'SELL'
    price:      float
    sl:         float
    tp:         float
    rsi:        float
    atr:        float
    confidence: float
    strategy:   str
    target_time:     Optional[str]   = field(default=None)
    target_datetime: Optional[str]   = field(default=None)
    target_bars:     Optional[float] = field(default=None)


class IStrategy(ABC):
    @property
    @abstractmethod
    def key(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def signals_per_day(self) -> str: ...

    @property
    @abstractmethod
    def best_for(self) -> str: ...

    @property
    @abstractmethod
    def style(self) -> str: ...

    @property
    @abstractmethod
    def color(self) -> str: ...

    @abstractmethod
    def generate(self, df: pd.DataFrame, ts_fn) -> List[Signal]: ...

    def to_dict(self) -> dict:
        return {
            "key":         self.key,
            "name":        self.name,
            "description": self.description,
            "signals_day": self.signals_per_day,
            "best_for":    self.best_for,
            "style":       self.style,
            "color":       self.color,
        }
