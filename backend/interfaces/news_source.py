from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class NewsArticle:
    title:     str
    source:    str
    url:       str
    age:       str
    timestamp: float
    category:  str
    icon:      str
    sentiment: str
    score:     int
    symbol:    str


class INewsSource(ABC):
    @abstractmethod
    def fetch(self, symbols: List[str], max_per_symbol: int = 5) -> List[NewsArticle]: ...
