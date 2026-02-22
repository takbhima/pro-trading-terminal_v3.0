from abc import ABC, abstractmethod


class INotifier(ABC):
    @abstractmethod
    def notify_signal(self, symbol: str, signal_type: str, price: float, sl: float, tp: float) -> None: ...

    @abstractmethod
    def notify_trade_exit(self, symbol: str, exit_reason: str, pnl: float, pnl_pct: float) -> None: ...
