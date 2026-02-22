from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class WatchlistItem:
    sym:  str
    name: str


class IWatchlistStore(ABC):
    @abstractmethod
    def load(self) -> List[WatchlistItem]: ...

    @abstractmethod
    def add(self, sym: str, name: str) -> dict: ...

    @abstractmethod
    def remove(self, sym: str) -> dict: ...
