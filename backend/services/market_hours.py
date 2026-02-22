import pytz
from datetime import datetime, timezone

_MARKET_HOURS = {
    "NSE":    (pytz.timezone("Asia/Kolkata"),     (9, 15),  (15, 30)),
    "NYSE":   (pytz.timezone("America/New_York"), (9, 30),  (16,  0)),
    "NASDAQ": (pytz.timezone("America/New_York"), (9, 30),  (16,  0)),
    "LSE":    (pytz.timezone("Europe/London"),    (8,  0),  (16, 30)),
}

_CRYPTO_SYMS = {
    "BTC-USD", "ETH-USD", "BNB-USD", "SOL-USD",
    "XRP-USD", "DOGE-USD", "GC=F", "SI=F", "CL=F", "NG=F",
}

_NSE_SYMS = {"^NSEI", "^NSEBANK", "^BSESN"}


class MarketHoursService:
    def open_markets(self) -> list[str]:
        now = datetime.now(timezone.utc)
        out = []
        for name, (tz, (oh, om), (ch, cm)) in _MARKET_HOURS.items():
            local = now.astimezone(tz)
            if local.weekday() >= 5:
                continue
            open_t  = local.replace(hour=oh, minute=om, second=0, microsecond=0)
            close_t = local.replace(hour=ch, minute=cm, second=0, microsecond=0)
            if open_t <= local <= close_t:
                out.append(name)
        return out

    def is_tradeable(self, symbol: str, open_mkt: list[str] = None) -> bool:
        if open_mkt is None:
            open_mkt = self.open_markets()
        if symbol in _CRYPTO_SYMS or symbol.endswith("=F"):
            return True
        is_nse = symbol.endswith(".NS") or symbol.endswith(".BO") or symbol in _NSE_SYMS
        is_us  = not is_nse and "." not in symbol.replace("-", "") and not symbol.startswith("^")
        if is_nse and "NSE"  in open_mkt: return True
        if is_us  and "NYSE" in open_mkt: return True
        return bool(open_mkt)
