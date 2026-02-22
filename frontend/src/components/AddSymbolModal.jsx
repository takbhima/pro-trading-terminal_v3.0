/**
 * AddSymbolModal — Enhanced with live symbol validation (E6).
 *
 * Enhancement 6: Before submitting to /api/watchlist, calls GET /api/validate
 * to confirm the ticker exists on Yahoo Finance and has a live price.
 * Also pre-fills the display name from yfinance longName when available.
 *
 * UX flow:
 *   1. User types ticker → blur or Enter triggers validation
 *   2. Validation status shown inline (✓ price / ✗ error)
 *   3. Suggested name auto-filled (user can override)
 *   4. Submit button disabled until ticker is validated
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { api } from "../services/api";

export default function AddSymbolModal({ onClose, onAdd }) {
  const [sym,        setSym]        = useState("");
  const [name,       setName]       = useState("");
  const [error,      setError]      = useState("");
  const [loading,    setLoading]    = useState(false);
  const [validating, setValidating] = useState(false);
  const [validation, setValidation] = useState(null); // { ok, price, suggested_name, reason }
  const symRef    = useRef(null);
  const nameRef   = useRef(null);
  const debounceRef = useRef(null);

  useEffect(() => { setTimeout(() => symRef.current?.focus(), 50); }, []);

  // E6: Validate ticker via API
  const validateTicker = useCallback(async (rawSym) => {
    const s = rawSym.trim().toUpperCase();
    if (!s) { setValidation(null); return; }

    setValidating(true);
    setValidation(null);
    setError("");
    try {
      const data = await api.validateSymbol(s);
      setValidation(data);
      if (data.ok && data.suggested_name && !name) {
        setName(data.suggested_name);
      }
      if (!data.ok) {
        setError(data.reason || "Symbol not found");
      }
    } catch (e) {
      setError("Validation failed: " + e.message);
    } finally {
      setValidating(false);
    }
  }, [name]);

  // Debounced auto-validate as user types
  const handleSymChange = (e) => {
    const val = e.target.value;
    setSym(val);
    setValidation(null);
    setError("");
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (val.trim().length >= 1) validateTicker(val);
    }, 800);
  };

  const handleSymBlur = () => {
    clearTimeout(debounceRef.current);
    if (sym.trim()) validateTicker(sym);
  };

  const confirm = async () => {
    const s = sym.trim().toUpperCase();
    const n = name.trim() || s;
    if (!s) { setError("Enter a ticker symbol"); return; }
    if (validation && !validation.ok) { setError(validation.reason); return; }

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

  // validation must have run (not null) and be ok before allowing submit
  const canSubmit = !loading && !validating && sym.trim().length > 0 && validation !== null && validation.ok;

  return (
    <div className="modal-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal-box">
        <h3>➕ Add to Watchlist</h3>

        {error && <div className="m-err">{error}</div>}

        <div className="m-sym-wrap">
          <input
            ref={symRef}
            className={`m-inp${validation ? (validation.ok ? " valid" : " invalid") : ""}`}
            placeholder="Yahoo ticker: AAPL, RELIANCE.NS, ^NSEI, BTC-USD"
            value={sym}
            onChange={handleSymChange}
            onBlur={handleSymBlur}
            onKeyDown={(e) => e.key === "Enter" && nameRef.current?.focus()}
          />
          {/* Validation status indicator */}
          <div className="m-val-status">
            {validating && <span className="m-val-checking">⏳ Checking…</span>}
            {!validating && validation?.ok && (
              <span className="m-val-ok">
                ✓ Valid · ₹{validation.price?.toLocaleString("en-IN")}
              </span>
            )}
            {!validating && validation && !validation.ok && (
              <span className="m-val-err">✗ Not found</span>
            )}
          </div>
        </div>

        <input
          ref={nameRef}
          id="m-name-inp"
          className="m-inp"
          placeholder="Display name (auto-filled from Yahoo Finance)"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && canSubmit && confirm()}
        />

        {validation?.ok && validation?.suggested_name && (
          <div className="m-hint">
            💡 <em>{validation.suggested_name}</em>
          </div>
        )}

        <div className="m-btns">
          <button className="m-ok" onClick={confirm} disabled={!canSubmit}>
            {loading ? "Adding…" : validating ? "Validating…" : "Add"}
          </button>
          <button className="m-cancel" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
