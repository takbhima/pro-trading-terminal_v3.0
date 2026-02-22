"""
MultiSourceNewsService — resilient multi-source news fetcher.

Fixes applied vs original:
  1. ET RSS URL changed to working endpoint (rss.cms was returning HTML not XML)
  2. DNS failures are cached per-session so we don't retry dead hosts every call
  3. XML is sanitised before parsing — strips illegal chars that break ET parser
  4. Malformed XML falls back to regex title extraction instead of crashing
  5. Timeout reduced to 4 s so slow hosts don't block the API response
  6. Noisy [NEWS] log lines suppressed for known-bad hosts; shown once only
"""

import re
import time
import socket
import xml.etree.ElementTree as ET
import urllib.request as _ur
from typing import List, Set

from backend.interfaces import INewsSource
from backend.interfaces.news_source import NewsArticle

# ── Category / sentiment tables ──────────────────────────────────────────────
_CATS = [
    (["result","profit","revenue","earnings","quarterly","q1","q2","q3","q4","fy","net income"], "Earnings",     "📊"),
    (["dividend","bonus","buyback","split","rights issue"],                                       "Corporate",    "💰"),
    (["merger","acquisition","takeover","deal","stake","buy out"],                                "M&A",          "🤝"),
    (["rbi","fed","sebi","rate","repo","inflation","gdp","policy","monetary"],                    "Policy",       "🏦"),
    (["war","crisis","sanction","geopolit","conflict","ukraine","russia","china","iran"],          "Geopolitical", "⚠️"),
    (["crash","circuit","halt","suspension","fraud","scam","default","bankruptcy"],               "Risk",         "🚨"),
    (["ipo","listing","nfo","fundraise","public offer"],                                           "IPO",          "🚀"),
    (["upgrade","downgrade","target","outperform","buy rating","sell rating","initiate"],          "Analyst",      "🎯"),
    (["nasdaq","dow jones","s&p","ftse","nikkei","world market","global market"],                 "Global Mkt",   "🌍"),
    (["oil","gold","crude","commodity","silver","currency","bitcoin","crypto"],                    "Commodity",    "🛢️"),
]
_POS = ["rise","rally","gain","surge","strong","beat","high","growth","bullish","outperform",
        "soar","jump","climb","boost","profit","positive","recovery","rebound"]
_NEG = ["fall","drop","loss","crash","decline","downgrade","weak","miss","cut","risk",
        "crisis","bearish","plunge","slump","concern","halt","fraud","disappoints","fear"]

# Hosts that failed DNS in this process lifetime — skip immediately next time
_DEAD_HOSTS: Set[str] = set()

# Regex fallback: extract <title> tags from raw XML text when ET parse fails
_TITLE_RE = re.compile(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.DOTALL)
_LINK_RE  = re.compile(r"<link>(.*?)</link>",  re.DOTALL)
_DATE_RE  = re.compile(r"<pubDate>(.*?)</pubDate>", re.DOTALL)

# Strip XML 1.0 illegal control characters (the cause of "syntax error: line 1, col 15")
_ILLEGAL_XML_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean_xml(raw: str) -> str:
    """Remove control characters that make ET choke, fix common ET RSS encoding."""
    return _ILLEGAL_XML_RE.sub("", raw)


def _strip_cdata(s: str) -> str:
    s = s.strip()
    if s.startswith("<![CDATA[") and s.endswith("]]>"):
        return s[9:-3].strip()
    return s


def _categorise(title: str):
    t = title.lower()
    for kws, cat, icon in _CATS:
        if any(k in t for k in kws):
            return cat, icon
    return "Market", "📰"


def _sentiment(title: str):
    t = title.lower()
    p = sum(1 for w in _POS if w in t)
    n = sum(1 for w in _NEG if w in t)
    if p > n:  return "positive", min(92, 55 + p * 10)
    if n > p:  return "negative", max(8,  45 - n * 10)
    return "neutral", 50


def _age(ts: float) -> str:
    s = time.time() - ts
    if s < 60:    return "just now"
    if s < 3600:  return f"{int(s/60)}m ago"
    if s < 86400: return f"{int(s/3600)}h ago"
    return f"{int(s/86400)}d ago"


def _parse_pubdate(pub: str) -> float:
    if not pub:
        return time.time() - 3600
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(pub.strip()).timestamp()
    except Exception:
        pass
    try:
        from datetime import datetime
        return datetime.fromisoformat(pub.strip().replace("Z", "+00:00")).timestamp()
    except Exception:
        return time.time() - 3600


def _make_article(title, source, url, ts, sym) -> NewsArticle:
    title = _strip_cdata(title)
    cat, icon   = _categorise(title)
    sent, score = _sentiment(title)
    return NewsArticle(
        title=title, source=source, url=url or "#",
        age=_age(ts), timestamp=ts,
        category=cat, icon=icon,
        sentiment=sent, score=score, symbol=sym,
    )


def _host_of(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).hostname or url
    except Exception:
        return url


def _fetch_url(url: str, timeout: int = 4) -> str | None:
    """
    Fetch URL text. Returns None (silently) if:
      - host already in _DEAD_HOSTS (DNS failed or HTTP 4xx previously)
      - DNS lookup fails now    → marks host dead, logs once
      - HTTP 4xx/403 error      → marks host dead, logs once
      - Any other network error → logs briefly, does NOT mark dead (may be transient)
    """
    host = _host_of(url)
    if host in _DEAD_HOSTS:
        return None
    try:
        req = _ur.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; NewsBot/1.0)",
            "Accept":     "application/rss+xml, application/xml, text/xml, */*",
        })
        with _ur.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except socket.gaierror:
        # DNS failure — permanent for this session
        _DEAD_HOSTS.add(host)
        print(f"[NEWS] Host unreachable (skipping for session): {host}")
        return None
    except _ur.HTTPError as e:
        if e.code in (403, 401, 404, 410):
            # Forbidden / not found — permanent, no point retrying
            _DEAD_HOSTS.add(host)
            print(f"[NEWS] HTTP {e.code} — skipping for session: {host}")
        else:
            # 5xx / rate-limit — transient, allow retry next call
            print(f"[NEWS] HTTP {e.code} on {url[:45]}")
        return None
    except Exception as e:
        short = str(e)[:60]
        print(f"[NEWS] Fetch failed {url[:45]}: {short}")
        return None


def _parse_rss_text(raw: str, sym: str, count: int, source_name: str) -> List[NewsArticle]:
    """
    Parse RSS XML text into articles.
    Strategy:
      1. Try ET on cleaned XML.
      2. If ET still fails, fall back to regex extraction.
    """
    cleaned = _clean_xml(raw)
    out: List[NewsArticle] = []

    # ── Strategy 1: proper XML parse ─────────────────────────────────────────
    try:
        root  = ET.fromstring(cleaned)
        items = root.findall(".//item")
        for item in items[:count]:
            title = _strip_cdata((item.findtext("title") or "").strip())
            if not title:
                continue
            link  = (item.findtext("link") or "#").strip()
            pub   = item.findtext("pubDate") or ""
            src   = item.findtext("source") or source_name
            out.append(_make_article(title, src, link, _parse_pubdate(pub), sym))
        return out
    except ET.ParseError:
        pass  # fall through to regex

    # ── Strategy 2: regex fallback ────────────────────────────────────────────
    titles = _TITLE_RE.findall(cleaned)
    links  = _LINK_RE.findall(cleaned)
    dates  = _DATE_RE.findall(cleaned)

    # titles[0] is usually the channel title — skip it
    for i, title in enumerate(titles[1 : count + 1]):
        title = _strip_cdata(title.strip())
        if not title:
            continue
        link = links[i + 1].strip() if i + 1 < len(links) else "#"
        pub  = dates[i].strip()     if i     < len(dates)  else ""
        out.append(_make_article(title, source_name, link, _parse_pubdate(pub), sym))

    return out


class MultiSourceNewsService(INewsSource):
    """
    Fetches news from multiple sources with graceful degradation.
    Sources tried in order:
      Per symbol : yfinance API → Yahoo Finance RSS
      General    : Moneycontrol RSS → Economic Times RSS → Reuters RSS
    Dead hosts are skipped for the lifetime of the process.
    """

    def fetch(self, symbols: List[str], max_per_symbol: int = 5) -> List[NewsArticle]:
        articles: List[NewsArticle] = []
        seen: set = set()

        def add(items: List[NewsArticle]) -> None:
            for a in items:
                key = a.title[:55].lower().strip()
                if key and key not in seen:
                    seen.add(key)
                    articles.append(a)

        for sym in symbols[:8]:
            items = self._yf_news(sym, max_per_symbol) or self._rss_yahoo(sym, max_per_symbol)
            add(items)

        for feed_fn in [self._rss_mc, self._rss_et, self._rss_reuters]:
            if len(articles) >= 15:
                break
            add(feed_fn(5))

        articles.sort(key=lambda a: a.timestamp, reverse=True)
        return articles[:25]

    # ── Per-symbol sources ────────────────────────────────────────────────────

    @staticmethod
    def _yf_news(sym: str, count: int) -> List[NewsArticle]:
        try:
            import yfinance as yf
            ticker = yf.Ticker(sym)
            try:
                raw = ticker.get_news(count=count)
            except TypeError:
                raw = ticker.get_news()
            if not raw:
                return []
            out = []
            for item in raw[:count]:
                # Support both old yfinance dict shape and new nested shape
                content = item.get("content") or {}
                title   = item.get("title") or content.get("title", "")
                if not title:
                    continue
                source  = (item.get("publisher")
                           or content.get("provider", {}).get("displayName", "Yahoo Finance"))
                url     = (item.get("link")
                           or content.get("canonicalUrl", {}).get("url", "#"))
                ts      = (item.get("providerPublishTime")
                           or content.get("pubDate")
                           or time.time())
                if isinstance(ts, str):
                    ts = _parse_pubdate(ts)
                out.append(_make_article(title, source, url, float(ts), sym))
            return out
        except Exception as e:
            print(f"[NEWS] yfinance {sym}: {str(e)[:80]}")
            return []

    @staticmethod
    def _rss_yahoo(sym: str, count: int) -> List[NewsArticle]:
        sym_enc = sym.replace("^", "%5E").replace("&", "%26")
        url     = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={sym_enc}&region=US&lang=en-US"
        raw     = _fetch_url(url)
        if not raw:
            return []
        return _parse_rss_text(raw, sym, count, "Yahoo Finance")

    # ── General / fallback sources ────────────────────────────────────────────

    @staticmethod
    def _rss_mc(count: int) -> List[NewsArticle]:
        raw = _fetch_url("https://www.moneycontrol.com/rss/latestnews.xml")
        if not raw:
            return []
        return _parse_rss_text(raw, "MC_GENERAL", count, "Moneycontrol")

    @staticmethod
    def _rss_et(count: int) -> List[NewsArticle]:
        # FIX: rss.cms returns an HTML redirect page, not XML.
        # Use the correct ET Markets RSS endpoint instead.
        raw = _fetch_url("https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms")
        if not raw:
            return []
        return _parse_rss_text(raw, "MARKET_GENERAL", count, "Economic Times")

    @staticmethod
    def _rss_reuters(count: int) -> List[NewsArticle]:
        # Reuters blocked their RSS; try alternative public business feed
        raw = _fetch_url("https://news.google.com/rss/search?q=business+india&hl=en-IN&gl=IN&ceid=IN:en")
        if not raw:
            # Silently skip — host is often unreachable outside US/EU
            return []
        return _parse_rss_text(raw, "GLOBAL_GENERAL", count, "Reuters")