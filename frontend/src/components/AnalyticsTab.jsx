/**
 * AnalyticsTab — E2: Display persistent PnL analytics from SQLite.
 *
 * Shows win rate, total PnL, best/worst trades, and per-strategy breakdown.
 * Data survives server restarts because it's backed by SQLite.
 */
import { useState, useEffect } from "react";
import { api } from "../services/api";
import { fmt } from "../utils/utils";

function StatBox({ label, value, color }) {
  return (
    <div className="stat-box">
      <div className="stat-lbl">{label}</div>
      <div className="stat-val" style={{ color: color || "var(--text)" }}>{value}</div>
    </div>
  );
}

export default function AnalyticsTab() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  const load = async () => {
    setLoading(true); setError(null);
    try {
      const d = await api.analytics();
      setData(d);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  if (loading) return <div className="analytics-empty">⏳ Loading analytics…</div>;
  if (error)   return <div className="analytics-empty" style={{ color: "var(--red)" }}>⚠ {error}</div>;
  if (!data)   return null;

  const { summary, by_strategy } = data;
  const winColor  = summary.win_rate >= 50 ? "var(--green)" : "var(--red)";
  const pnlColor  = summary.total_pnl >= 0 ? "var(--green)" : "var(--red)";

  return (
    <div className="analytics-panel">
      <div className="analytics-header">
        <span className="analytics-title">📊 Trade Analytics</span>
        <button className="analytics-refresh" onClick={load}>↻ Refresh</button>
      </div>

      {summary.total === 0 ? (
        <div className="analytics-empty">No closed trades yet. Trade history will appear here after your first exit.</div>
      ) : (
        <>
          <div className="stat-grid">
            <StatBox label="Total Trades"  value={summary.total} />
            <StatBox label="Win Rate"      value={`${summary.win_rate}%`} color={winColor} />
            <StatBox label="Wins"          value={summary.wins}   color="var(--green)" />
            <StatBox label="Losses"        value={summary.losses} color="var(--red)" />
            <StatBox label="Total P&L"     value={fmt(summary.total_pnl)} color={pnlColor} />
            <StatBox label="Avg P&L"       value={fmt(summary.avg_pnl)}   color={summary.avg_pnl >= 0 ? "var(--green)" : "var(--red)"} />
            <StatBox label="Best Trade"    value={fmt(summary.best)}   color="var(--green)" />
            <StatBox label="Worst Trade"   value={fmt(summary.worst)}  color="var(--red)" />
          </div>

          <div className="win-bar-wrap">
            <div className="win-bar" style={{ width: `${summary.win_rate}%` }} />
            <div className="loss-bar" style={{ width: `${100 - summary.win_rate}%` }} />
          </div>
          <div className="win-bar-labels">
            <span style={{ color: "var(--green)" }}>Win {summary.win_rate}%</span>
            <span style={{ color: "var(--red)" }}>Loss {(100 - summary.win_rate).toFixed(1)}%</span>
          </div>

          {Object.keys(by_strategy).length > 0 && (
            <div className="strat-breakdown">
              <div className="sb-title">By Strategy</div>
              {Object.entries(by_strategy).map(([strat, s]) => {
                const wr = s.wins + s.losses > 0
                  ? Math.round(s.wins / (s.wins + s.losses) * 100)
                  : 0;
                return (
                  <div key={strat} className="sb-row">
                    <span className="sb-strat">{strat}</span>
                    <span className="sb-wr" style={{ color: wr >= 50 ? "var(--green)" : "var(--red)" }}>
                      {wr}% WR
                    </span>
                    <span className="sb-pnl" style={{ color: s.total_pnl >= 0 ? "var(--green)" : "var(--red)" }}>
                      {s.total_pnl >= 0 ? "+" : ""}{fmt(s.total_pnl)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
