"""
Interfaces package — all abstract base classes live here.
Every concrete class depends on these abstractions, never on each other directly.
(Dependency Inversion Principle)
"""
from .data_source      import IDataSource
from .indicator        import IIndicator
from .strategy         import IStrategy, Signal
from .news_source      import INewsSource, NewsArticle
from .trade_store      import ITradeStore
from .watchlist_store  import IWatchlistStore
from .predictor        import IPredictor, Prediction
from .notifier         import INotifier

__all__ = [
    "IDataSource",
    "IIndicator",
    "IStrategy", "Signal",
    "INewsSource", "NewsArticle",
    "ITradeStore",
    "IWatchlistStore",
    "IPredictor", "Prediction",
    "INotifier",
]
