/**
 * StrategyBar — Strategy selector + MTF confirmation toggle (E4).
 *
 * Enhancement 4: "MTF Confirm" toggle button lets users require that
 * a signal on the current timeframe must align with the daily trend
 * (EMA9 > EMA21 on 1D). This cuts false signals at the cost of fewer trades.
 * State is lifted to App so ChartPanel/useChartData can pass it to the API.
 */
import { useStrategies } from "../hooks/useStrategies";

export default function StrategyBar({ activeStrategy, onStrategyChange, mtfEnabled, onMtfToggle }) {
  const { strategies } = useStrategies();
  const active = strategies.find((s) => s.key === activeStrategy);

  return (
    <div className="strat-bar">
      <span className="strat-lbl">Strategy:</span>
      {strategies.map((s) => (
        <button
          key={s.key}
          className={`strat-btn${s.key === activeStrategy ? " active" : ""}`}
          style={s.key === activeStrategy ? {
            background:   `${s.color}22`,
            borderColor:  s.color,
            color:        s.color,
          } : {}}
          title={`${s.description}\nBest: ${s.best_for} | ~${s.signals_day} signals/day`}
          onClick={() => onStrategyChange(s.key)}
        >
          <span className="s-dot" style={{ background: s.color }} />
          {s.name}
          <span className="s-badge">{s.signals_day}</span>
        </button>
      ))}
      {active && (
        <span className="strat-info">
          {active.style} · {active.best_for} · ~{active.signals_day}/day
        </span>
      )}

      {/* E4 — MTF Confirmation Toggle */}
      <button
        className={`mtf-toggle${mtfEnabled ? " active" : ""}`}
        title={
          mtfEnabled
            ? "MTF Confirm ON — signals must align with daily trend (EMA9>EMA21 on 1D). Click to disable."
            : "MTF Confirm OFF — enable to require daily trend alignment before showing signals."
        }
        onClick={onMtfToggle}
      >
        <span className="mtf-icon">{mtfEnabled ? "🔒" : "🔓"}</span>
        MTF Confirm
        <span className={`mtf-badge ${mtfEnabled ? "on" : "off"}`}>
          {mtfEnabled ? "ON" : "OFF"}
        </span>
      </button>
    </div>
  );
}
