import json
import os
from typing import List

from backend.interfaces.watchlist_store import IWatchlistStore, WatchlistItem

_DEFAULTS = [
    WatchlistItem("^BSESN",      "SENSEX"),
    WatchlistItem("^NSEBANK",    "Bank Nifty"),
    WatchlistItem("^NSEI",       "Nifty 50"),
    WatchlistItem("RELIANCE.NS", "Reliance"),
    WatchlistItem("TCS.NS",      "TCS"),
    WatchlistItem("INFY.NS",     "Infosys"),
    WatchlistItem("HDFCBANK.NS", "HDFC Bank"),
    WatchlistItem("AAPL",        "Apple"),
    WatchlistItem("MSFT",        "Microsoft"),
    WatchlistItem("NVDA",        "Nvidia"),
    WatchlistItem("BTC-USD",     "Bitcoin"),
]


class JsonWatchlistStore(IWatchlistStore):
    def __init__(self, filepath: str):
        self._path = filepath

    def load(self) -> List[WatchlistItem]:
        try:
            if os.path.exists(self._path):
                with open(self._path) as f:
                    raw = json.load(f)
                return [WatchlistItem(r["sym"], r.get("name", r["sym"])) for r in raw]
        except Exception as e:
            print(f"[WL] Load error: {e}")
        self._save(_DEFAULTS)
        return list(_DEFAULTS)

    def add(self, sym: str, name: str) -> dict:
        sym = sym.upper().strip()
        items = self.load()
        if any(w.sym == sym for w in items):
            return {"ok": False, "reason": f"{sym} already in watchlist"}
        items.append(WatchlistItem(sym, name or sym))
        self._save(items)
        return {"ok": True, "watchlist": [{"sym": w.sym, "name": w.name} for w in items]}

    def remove(self, sym: str) -> dict:
        sym   = sym.upper().strip()
        items = [w for w in self.load() if w.sym != sym]
        self._save(items)
        return {"ok": True, "watchlist": [{"sym": w.sym, "name": w.name} for w in items]}

    def _save(self, items: List[WatchlistItem]) -> None:
        try:
            with open(self._path, "w") as f:
                json.dump([{"sym": w.sym, "name": w.name} for w in items], f, indent=2)
        except Exception as e:
            print(f"[WL] Save error: {e}")
