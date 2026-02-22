/**
 * Sidebar — Single Responsibility: tab navigation container.
 * Each tab panel is its own component (SRP).
 *
 * BUG FIX: Now receives `strategy` prop and passes it to SignalTab.
 * Previously SignalTab had no way to know the active strategy and
 * hardcoded "pro_mtf" in its own useChartData call, so the signal
 * panel was always wrong when any other strategy was selected.
 */
import { useState } from "react";
import SignalTab  from "./SignalTab";
import NewsTab    from "./NewsTab";
import PredictTab from "./PredictTab";

const TABS = [
  { id: "signal",  label: "📌 Signal"  },
  { id: "news",    label: "📰 News"    },
  { id: "predict", label: "🤖 Predict" },
];

export default function Sidebar({ symbol, interval, strategy }) {
  const [activeTab, setActiveTab] = useState("signal");

  return (
    <aside className="sidebar">
      <div className="sb-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={`sb-tab${activeTab === t.id ? " active" : ""}`}
            onClick={() => setActiveTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className={`sb-panel${activeTab === "signal"  ? " active" : ""}`}>
        {/* Pass strategy down so SignalTab fetches the correct strategy's signals */}
        <SignalTab symbol={symbol} interval={interval} strategy={strategy} />
      </div>
      <div className={`sb-panel${activeTab === "news"    ? " active" : ""}`}>
        {activeTab === "news"    && <NewsTab symbol={symbol} />}
      </div>
      <div className={`sb-panel${activeTab === "predict" ? " active" : ""}`}>
        {activeTab === "predict" && <PredictTab symbol={symbol} interval={interval} />}
      </div>
    </aside>
  );
}
