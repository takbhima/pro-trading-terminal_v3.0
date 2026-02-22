from typing import Dict, List, Optional
from backend.interfaces import IStrategy
from .implementations import (
    ProMTFStrategy,
    VWAPEMAStrategy,
    RSIReversalStrategy,
    BollingerBreakoutStrategy,
    MACDCrossoverStrategy,
    SupertrendScalperStrategy,
)


class StrategyRegistry:
    def __init__(self):
        self._strategies: Dict[str, IStrategy] = {}

    def register(self, strategy: IStrategy) -> "StrategyRegistry":
        self._strategies[strategy.key] = strategy
        return self

    def get(self, key: str) -> Optional[IStrategy]:
        return self._strategies.get(key)

    def all(self) -> List[IStrategy]:
        return list(self._strategies.values())

    def keys(self) -> List[str]:
        return list(self._strategies.keys())

    def to_list(self) -> List[dict]:
        return [s.to_dict() for s in self._strategies.values()]


registry = (
    StrategyRegistry()
    .register(ProMTFStrategy())
    .register(VWAPEMAStrategy())
    .register(RSIReversalStrategy())
    .register(BollingerBreakoutStrategy())
    .register(MACDCrossoverStrategy())
    .register(SupertrendScalperStrategy())
)
