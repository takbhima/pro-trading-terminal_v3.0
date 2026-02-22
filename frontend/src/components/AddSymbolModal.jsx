/**
 * AddSymbolModal — Single Responsibility: collect + validate new watchlist symbol.
 */
import { useState, useEffect, useRef } from "react";
import { api } from "../services/api";

export default function AddSymbolModal({ onClose, onAdd }) {
  const [sym,     setSym]     = useState("");
  const [name,    setName]    = useState("");
  const [error,   setError]   = useState("");
  const [loading, setLoading] = useState(false);
  const symRef = useRef(null);

  useEffect(() => { setTimeout(() => symRef.current?.focus(), 50); }, []);

  const confirm = async () => {
    const s = sym.trim().toUpperCase();
    const n = name.trim() || s;
    if (!s) { setError("Enter a ticker symbol"); return; }
    setLoading(true); setError("");
    try {
      const data = await api.addWatchlist(s, n);
      if (!data.ok) { setError(data.reason || "Already in watchlist"); return; }
      onAdd(s, n);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-box">
        <h3>➕ Add to Watchlist</h3>
        {error && <div className="m-err">{error}</div>}
        <input
          ref={symRef}
          className="m-inp"
          placeholder="Yahoo ticker: AAPL, RELIANCE.NS, ^NSEI"
          value={sym}
          onChange={(e) => setSym(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && document.getElementById("m-name-inp")?.focus()}
        />
        <input
          id="m-name-inp"
          className="m-inp"
          placeholder="Display name (e.g. Apple Inc)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && confirm()}
        />
        <div className="m-btns">
          <button className="m-ok" onClick={confirm} disabled={loading}>
            {loading ? "Adding…" : "Add"}
          </button>
          <button className="m-cancel" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
