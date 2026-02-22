/**
 * PredictTab — Single Responsibility: display ML/technical direction prediction.
 * FIX: auto-loads on mount and whenever symbol or interval changes.
 */
import { useState, useCallback, useEffect, useRef } from "react";
import { api } from "../services/api";
import { fmt } from "../utils/utils";

export default function PredictTab({ symbol, interval }) {
  const [pred,    setPred]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const loadedKeyRef = useRef(null);  // track symbol+interval that was last loaded

  const load = useCallback(async (sym, iv) => {
    setLoading(true); setError(null);
    try {
      const data = await api.predict(sym, iv);
      if (data.error) throw new Error(data.error);
      setPred(data);
      loadedKeyRef.current = `${sym}__${iv}`;
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  // Auto-load on mount and whenever symbol or interval changes
  useEffect(() => {
    if (!symbol?.yahoo) return;
    const key = `${symbol.yahoo}__${interval}`;
    if (loadedKeyRef.current === key) return; // already loaded for this combo
    setPred(null);  // clear stale prediction from previous symbol
    load(symbol.yahoo, interval);
  }, [symbol?.yahoo, interval, load]);

  const dirColor = !pred ? "var(--subtext)"
    : pred.direction === "BULLISH" ? "var(--green)"
    : pred.direction === "BEARISH" ? "var(--red)"
    : "var(--yellow)";

  return (
    <div className="pred-panel">
      <div className="pred-sym-row">
        <span className="pred-sym-lbl">{symbol.label}</span>
        <button className="pred-refresh-btn" onClick={() => load(symbol.yahoo, interval)} disabled={loading}>
          {loading ? "⏳" : "↻"} Analyse
        </button>
      </div>

      {error && <div className="pred-error">⚠ {error}</div>}

      {loading && !pred && (
        <div className="pred-empty">⏳ Analysing {symbol.label}…</div>
      )}

      {!pred && !loading && !error && (
        <div className="pred-empty">No analysis yet for {symbol.label}</div>
      )}

      {pred && (
        <>
          <div className="pred-header">
            <div className="pred-dir" style={{ color: dirColor }}>
              {pred.direction === "BULLISH" ? "▲" : pred.direction === "BEARISH" ? "▼" : "●"} {pred.direction}
            </div>
            <div className="pred-conf-bar-wrap">
              <div className="pred-conf-bar" style={{ width: `${pred.confidence}%`, background: dirColor }} />
            </div>
            <div className="pred-conf-lbl">
              Overall Confidence: <b style={{ color: dirColor }}>{pred.confidence}%</b>
            </div>
          </div>

          <div className="score-row">
            {[
              { label: "Tech Score", val: pred.tech_score },
              { label: "News Score", val: pred.news_score },
              { label: "RSI",        val: pred.rsi        },
            ].map(({ label, val }) => (
              <div key={label} className="score-box">
                <div className="s-lbl">{label}</div>
                <div className="s-val" style={{
                  color: val > 60 ? "var(--green)" : val < 40 ? "var(--red)" : "var(--yellow)",
                }}>
                  {val}
                </div>
              </div>
            ))}
          </div>

          <div className="pred-targets">
            {[
              { label: "Target 1", val: pred.tp1, color: dirColor },
              { label: "Target 2", val: pred.tp2, color: dirColor },
              { label: "Stop Loss", val: pred.sl, color: "var(--red)" },
            ].map(({ label, val, color }) => (
              <div key={label} className="pt">
                <div className="pt-lbl">{label}</div>
                <div className="pt-val" style={{ color }}>{fmt(val)}</div>
              </div>
            ))}
          </div>

          <div className="pred-reasons">
            <div className="pr-title">📊 Technical Analysis</div>
            {pred.bull_reasons?.map((r, i) => (
              <div key={i} className="pr-item bull">▲ {r}</div>
            ))}
            {pred.bear_reasons?.map((r, i) => (
              <div key={i} className="pr-item bear">▼ {r}</div>
            ))}
          </div>

          <div className="pred-disclaimer">
            ⚠️ For educational purposes only. Not financial advice.
          </div>
        </>
      )}
    </div>
  );
}
