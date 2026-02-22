from abc import ABC, abstractmethod
import pandas as pd


class IDataSource(ABC):
    @abstractmethod
    def fetch(self, symbol: str, interval: str, period: str = None) -> pd.DataFrame: ...

    @abstractmethod
    def get_live_price(self, symbol: str) -> float: ...

    @abstractmethod
    def get_prev_close(self, symbol: str) -> float: ...
