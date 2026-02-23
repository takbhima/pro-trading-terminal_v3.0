/**
 * useWatchlist — FIX: adds clearAllSignals() so Watchlist can wipe
 * all signal badges when the strategy changes.
 */
import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";

export function useWatchlist() {
  const [items,   setItems]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [signals, setSignals] = useState({});  // sym → 'BUY' | 'SELL' | 'NONE'

  const load = useCallback(() => {
    api.watchlist()
      .then(setItems)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const add = useCallback(async (sym, name) => {
    const data = await api.addWatchlist(sym, name);
    if (data.ok) setItems(data.watchlist);
    return data;
  }, []);

  const remove = useCallback(async (sym) => {
    await api.removeWatchlist(sym);
    setItems(prev => prev.filter(w => w.sym !== sym));
  }, []);

  const setSignal = useCallback((sym, type) => {
    setSignals(prev => ({ ...prev, [sym]: type }));
  }, []);

  // FIX: reset every symbol's badge to NONE (called on strategy/interval change)
  const clearAllSignals = useCallback(() => {
    setSignals({});
  }, []);

  return { items, loading, signals, add, remove, setSignal, clearAllSignals, reload: load };
}
