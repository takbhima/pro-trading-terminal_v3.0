/**
 * Sidebar — Single Responsibility: tab navigation container.
 * Each tab panel is its own component (SRP).
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

export default function Sidebar({ symbol, interval }) {
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
        <SignalTab symbol={symbol} interval={interval} />
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
