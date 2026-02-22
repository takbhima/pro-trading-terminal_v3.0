"""
SymbolValidator — validates that a Yahoo Finance ticker is real and tradeable
before adding it to the watchlist.

Checks:
  1. yf.Ticker(sym).fast_info.last_price > 0
  2. Reasonable name resolution (not empty)
  3. Returns a suggested display name from longName / shortName if none provided
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ValidationResult:
    ok:          bool
    reason:      str = ""
    price:       float = 0.0
    suggested_name: str = ""


def validate_symbol(sym: str) -> ValidationResult:
    """
    Returns ValidationResult.
    ok=True  → symbol exists and has a live price.
    ok=False → reason explains why it failed.
    """
    sym = sym.strip().upper()
    if not sym:
        return ValidationResult(ok=False, reason="Symbol cannot be empty")
    if len(sym) > 20:
        return ValidationResult(ok=False, reason="Symbol too long (max 20 chars)")

    try:
        import yfinance as yf
        ticker = yf.Ticker(sym)

        # fast_info is a lightweight call — no full history needed
        info  = ticker.fast_info
        price = float(
            getattr(info, "last_price", None)
            or getattr(info, "regular_market_price", None)
            or 0
        )

        if price <= 0:
            # Try previous_close as a fallback — some off-hours indices only have this
            price = float(getattr(info, "previous_close", 0) or 0)

        if price <= 0:
            return ValidationResult(
                ok=False,
                reason=f"'{sym}' returned no price data — check the ticker symbol",
            )

        # Try to get a human-readable name
        suggested = sym
        try:
            full_info = ticker.info  # slightly heavier but only called on add
            suggested = (
                full_info.get("longName")
                or full_info.get("shortName")
                or full_info.get("name")
                or sym
            )
        except Exception:
            pass

        return ValidationResult(
            ok=True,
            price=round(price, 4),
            suggested_name=suggested,
        )

    except Exception as e:
        short = str(e)[:120]
        return ValidationResult(ok=False, reason=f"Lookup failed: {short}")
