/**
 * StrategyBar — Single Responsibility: display + select trading strategies.
 */
import { useStrategies } from "../hooks/useStrategies";

export default function StrategyBar({ activeStrategy, onStrategyChange }) {
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
    </div>
  );
}
