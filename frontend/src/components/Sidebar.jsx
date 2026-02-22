/**
 * Sidebar — Tab container with added Analytics tab (E2).
 *
 * Enhancement 2: AnalyticsTab shows persistent SQLite-backed PnL history.
 * Enhancement 4: requireMtf prop passed through to SignalTab.
 */
import { useState } from "react";
import SignalTab    from "./SignalTab";
import NewsTab      from "./NewsTab";
import PredictTab   from "./PredictTab";
import AnalyticsTab from "./AnalyticsTab";

const TABS = [
  { id: "signal",    label: "📌 Signal"    },
  { id: "news",      label: "📰 News"      },
  { id: "predict",   label: "🤖 Predict"   },
  { id: "analytics", label: "📊 Analytics" },  // E2
];

export default function Sidebar({ symbol, interval, strategy, requireMtf, fetchKey = 0 }) {
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

      <div className={`sb-panel${activeTab === "signal"    ? " active" : ""}`}>
        <SignalTab symbol={symbol} interval={interval} strategy={strategy} requireMtf={requireMtf} fetchKey={fetchKey} />
      </div>
      <div className={`sb-panel${activeTab === "news"      ? " active" : ""}`}>
        {activeTab === "news"      && <NewsTab symbol={symbol} />}
      </div>
      <div className={`sb-panel${activeTab === "predict"   ? " active" : ""}`}>
        {activeTab === "predict"   && <PredictTab symbol={symbol} interval={interval} />}
      </div>
      <div className={`sb-panel${activeTab === "analytics" ? " active" : ""}`}>
        {activeTab === "analytics" && <AnalyticsTab />}
      </div>
    </aside>
  );
}
