/**
 * MarketTicker — Compact live ticker strip showing SENSEX, Nifty 50, Bank Nifty.
 *
 * Polls GET /api/market-ticker every 15 seconds.
 * Displays: name | price | change | change% — colour-coded green/red.
 * Animates value changes with a brief flash.
 * Falls back gracefully if markets are closed (shows last known values).
 */
import { useState, useEffect, useRef } from "react";

const REFRESH_MS = 15_000; // 15 seconds

function TickerItem({ item }) {
  const isUp    = item.change >= 0;
  const prevRef = useRef(null);
  const [flash, setFlash] = useState(null); // "up" | "down" | null

  // Flash animation on price change
  useEffect(() => {
    if (prevRef.current !== null && prevRef.current !== item.price) {
      const dir = item.price > prevRef.current ? "up" : "down";
      setFlash(dir);
      const t = setTimeout(() => setFlash(null), 600);
      prevRef.current = item.price;
      return () => clearTimeout(t);
    }
    prevRef.current = item.price;
  }, [item.price]);

  const color  = isUp ? "var(--green)" : "var(--red)";
  const arrow  = isUp ? "▲" : "▼";
  const sign   = isUp ? "+" : "";

  return (
    <div className={`ticker-item${flash ? ` flash-${flash}` : ""}`}>
      <span className="ticker-name">{item.name}</span>
      <span className="ticker-price" style={{ color }}>
        {item.price?.toLocaleString("en-IN", { maximumFractionDigits: 2 })}
      </span>
      <span className="ticker-change" style={{ color }}>
        {arrow} {sign}{item.change?.toFixed(2)} ({sign}{item.change_pct?.toFixed(2)}%)
      </span>
    </div>
  );
}

export default function MarketTicker() {
  const [items,   setItems]   = useState([]);
  const [lastAt,  setLastAt]  = useState(null);
  const [error,   setError]   = useState(false);
  const timerRef = useRef(null);

  const fetchTicker = async () => {
    try {
      const res = await fetch("/api/market-ticker");
      if (!res.ok) throw new Error("fetch failed");
      const data = await res.json();
      if (data.indices?.length) {
        setItems(data.indices);
        setLastAt(new Date());
        setError(false);
      }
    } catch {
      setError(true);
    }
  };

  useEffect(() => {
    fetchTicker();
    timerRef.current = setInterval(fetchTicker, REFRESH_MS);
    return () => clearInterval(timerRef.current);
  }, []);

  if (!items.length && !error) {
    return (
      <div className="market-ticker loading">
        <span className="ticker-loading">⏳ Loading market data…</span>
      </div>
    );
  }

  return (
    <div className="market-ticker">
      <div className="ticker-label">LIVE</div>
      <div className="ticker-strip">
        {items.map((item) => (
          <TickerItem key={item.symbol} item={item} />
        ))}
      </div>
      {lastAt && (
        <div className="ticker-ts">
          Updated {lastAt.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
        </div>
      )}
      {error && <div className="ticker-err">⚠ Update failed — retrying…</div>}
    </div>
  );
}
