/**
 * NewsTab — Single Responsibility: fetch + display news articles.
 * FIX: auto-loads on mount and whenever symbol changes. Manual refresh still available.
 */
import { useState, useCallback, useEffect, useRef } from "react";
import { api } from "../services/api";

function NewsCard({ article: n }) {
  return (
    <a className={`news-card ${n.sentiment}`} href={n.url} target="_blank" rel="noopener noreferrer">
      <div className="news-top">
        <span className="news-cat">{n.icon} {n.category}</span>
        <span className="news-age">{n.age}</span>
      </div>
      <div className="news-title">{n.title}</div>
      <div className="news-bottom">
        <span className="news-src">{n.source}</span>
        <div className="news-meta">
          <span className="news-sym">{n.symbol}</span>
          <span className={`news-sent ${n.sentiment}`}>
            {n.sentiment === "positive" ? "▲ Bullish" : n.sentiment === "negative" ? "▼ Bearish" : "● Neutral"}
          </span>
        </div>
      </div>
    </a>
  );
}

export default function NewsTab({ symbol }) {
  const [articles, setArticles] = useState([]);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState(null);
  const [loadedAt, setLoadedAt] = useState(null);
  const loadedSymRef = useRef(null);   // track which symbol was last loaded

  const load = useCallback(async (sym) => {
    setLoading(true); setError(null);
    try {
      const data = await api.news([sym]);
      setArticles(data.news || []);
      setLoadedAt(new Date().toLocaleTimeString());
      loadedSymRef.current = sym;
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-load on mount and whenever the symbol changes
  useEffect(() => {
    if (!symbol?.yahoo) return;
    if (loadedSymRef.current === symbol.yahoo) return; // already loaded for this symbol
    load(symbol.yahoo);
  }, [symbol?.yahoo, load]);

  return (
    <div className="news-panel">
      <div className="news-refresh">
        <span className="news-ts">
          {loadedAt
            ? `${articles.length} articles · ${loadedAt}`
            : loading ? "Loading news…" : ""}
        </span>
        <button className="news-refresh-btn" onClick={() => load(symbol.yahoo)} disabled={loading}>
          {loading ? "⏳" : "↻"} Refresh
        </button>
      </div>

      {error && <div className="news-error">⚠ {error}</div>}

      {loading && !articles.length && (
        <div className="news-empty">⏳ Loading news for {symbol.label}…</div>
      )}

      {!loading && !articles.length && !error && (
        <div className="news-empty">No news found for {symbol.label}</div>
      )}

      {articles.map((a, i) => <NewsCard key={i} article={a} />)}
    </div>
  );
}
