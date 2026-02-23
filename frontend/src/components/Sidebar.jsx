/**
 * Sidebar.jsx
 * NEW: accepts onJumpToSignal prop from App.jsx and passes it
 * to SignalTab so clicking a signal history card scrolls the
 * main chart to that signal's timestamp.
 *
 * All other behaviour is unchanged — this is a drop-in replacement.
 * Tabs: Signal → News → Predict → Analytics
 */
import { useState } from "react";
import SignalTab     from "./SignalTab";
import NewsTab       from "./NewsTab";
import PredictTab    from "./PredictTab";
import AnalyticsTab  from "./AnalyticsTab";

const TABS = ["Signal", "News", "Predict", "Analytics"];

export default function Sidebar({
  symbol,
  interval,
  strategy,
  requireMtf,
  fetchKey,
  onJumpToSignal,   // NEW: callback(time, signal_id) → App.jsx → ChartPanel
}) {
  const [activeTab, setActiveTab] = useState("Signal");

  return (
    <aside className="sidebar">
      <div className="tab-bar">
        {TABS.map((t) => (
          <button
            key={t}
            className={`tab-btn${activeTab === t ? " active" : ""}`}
            onClick={() => setActiveTab(t)}
          >
            {t === "Signal"   && "📊 "}
            {t === "News"     && "📰 "}
            {t === "Predict"  && "🔮 "}
            {t === "Analytics"&& "📈 "}
            {t}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {activeTab === "Signal" && (
          <SignalTab
            symbol={symbol}
            interval={interval}
            strategy={strategy}
            requireMtf={requireMtf}
            fetchKey={fetchKey}
            onJumpToSignal={onJumpToSignal}  // NEW: pass through
          />
        )}
        {activeTab === "News" && (
          <NewsTab symbol={symbol} />
        )}
        {activeTab === "Predict" && (
          <PredictTab
            symbol={symbol}
            interval={interval}
          />
        )}
        {activeTab === "Analytics" && (
          <AnalyticsTab
            symbol={symbol}
            interval={interval}
            strategy={strategy}
            fetchKey={fetchKey}
          />
        )}
      </div>
    </aside>
  );
}
