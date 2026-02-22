from typing import Optional, List
from backend.interfaces.trade_store import ITradeStore, Trade, TradeExit


class InMemoryTradeStore(ITradeStore):
    def __init__(self):
        self._active:  dict[str, Trade]           = {}
        self._history: dict[str, list[TradeExit]] = {}

    def save_active(self, trade: Trade) -> None:
        self._active[trade.symbol] = trade

    def get_active(self, symbol: str) -> Optional[Trade]:
        return self._active.get(symbol)

    def get_all_active(self) -> List[Trade]:
        return list(self._active.values())

    def remove_active(self, symbol: str) -> Optional[Trade]:
        return self._active.pop(symbol, None)

    def save_closed(self, exit: TradeExit) -> None:
        if exit.symbol not in self._history:
            self._history[exit.symbol] = []
        self._history[exit.symbol].insert(0, exit)
        if len(self._history[exit.symbol]) > 20:
            self._history[exit.symbol].pop()

    def get_history(self, symbol: Optional[str] = None) -> List[TradeExit]:
        if symbol:
            return list(self._history.get(symbol, []))
        all_exits = []
        for exits in self._history.values():
            all_exits.extend(exits)
        all_exits.sort(key=lambda x: x.exit_time, reverse=True)
        return all_exits[:100]
