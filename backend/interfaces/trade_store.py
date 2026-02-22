from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List
from datetime import datetime


@dataclass
class Trade:
    symbol:                 str
    timeframe:              str
    strategy:               str
    side:                   str
    entry_price:            float
    target_price:           float
    stop_loss:              float
    confidence:             float
    entry_time:             datetime
    expected_time_minutes:  float
    expected_bars:          float
    rsi:                    float
    atr:                    float
    status:                 str = 'ACTIVE'


@dataclass
class TradeExit:
    symbol:           str
    side:             str
    strategy:         str
    timeframe:        str
    entry_price:      float
    exit_price:       float
    target_price:     float
    stop_loss:        float
    exit_reason:      str
    pnl:              float
    pnl_pct:          float
    duration_minutes: float
    entry_time:       str
    exit_time:        str
    confidence:       float


class ITradeStore(ABC):
    @abstractmethod
    def save_active(self, trade: Trade) -> None: ...

    @abstractmethod
    def get_active(self, symbol: str) -> Optional[Trade]: ...

    @abstractmethod
    def get_all_active(self) -> List[Trade]: ...

    @abstractmethod
    def remove_active(self, symbol: str) -> Optional[Trade]: ...

    @abstractmethod
    def save_closed(self, exit: TradeExit) -> None: ...

    @abstractmethod
    def get_history(self, symbol: Optional[str] = None) -> List[TradeExit]: ...
