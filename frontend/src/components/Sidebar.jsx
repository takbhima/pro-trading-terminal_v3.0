/**
 * Sidebar.jsx
 * FIX: Now passes `interval` prop to WatchlistSignalsTab so Radar
 *      shows signals for the SAME timeframe as the chart.
 *
 * Previously: WatchlistSignalsTab received no interval → defaulted to "1d"
 *             which is why Radar always showed 1D signals even on 1m charts.
 *
 * Also accepts onJumpToSignal prop from App.jsx and passes it
 * to SignalTab so clicking a signal history card scrolls the
 * main chart to that signal's timestamp.
 *
 * Tabs: Signal → Radar → News → Predict → Analytics
 */
import { useState } from "react";
import SignalTab           from "./SignalTab";
import WatchlistSignalsTab from "./WatchlistSignalsTab";
import NewsTab             from "./NewsTab";
import PredictTab          from "./PredictTab";
import AnalyticsTab        from "./AnalyticsTab";

const TABS = ["Signal", "Radar", "News", "Predict", "Analytics"];

export default function Sidebar({
  symbol,
  interval,       // FIX: now forwarded to WatchlistSignalsTab
  strategy,
  requireMtf,
  fetchKey,
  onJumpToSignal, // callback(time, signal_id, yahoo, label) → App.jsx → ChartPanel
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
            {t === "Signal"    && "📊 "}
            {t === "Radar"     && "📡 "}
            {t === "News"      && "📰 "}
            {t === "Predict"   && "🔮 "}
            {t === "Analytics" && "📈 "}
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
            onJumpToSignal={onJumpToSignal}
          />
        )}
        {activeTab === "Radar" && (
          <WatchlistSignalsTab
            interval={interval}    // FIX: was missing — Radar now tracks chart timeframe
            strategy={strategy}
            requireMtf={requireMtf}
            onJumpToSignal={onJumpToSignal}
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