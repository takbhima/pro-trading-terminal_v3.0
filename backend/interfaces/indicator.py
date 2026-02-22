from abc import ABC, abstractmethod
import pandas as pd


class IIndicator(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.Series: ...
