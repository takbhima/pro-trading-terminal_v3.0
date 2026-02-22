/**
 * SignalTab — Single Responsibility: display latest signal, active trade, exit events.
 * BUG FIXES applied:
 *  1. activeTrade PnL class was always "profit" due to wrong ternary
 *  2. exit history template literal had unmatched quote `var(--red'`
 *  3. Signal WHY uses pure utility function, not inline template strings
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { useWebSocket }  from "../context/WebSocketContext";
import { useTrade }      from "../context/TradeContext";
import { useChartData }  from "../hooks/useChartData";
import { fmt, elapsedMins, getWhyReasons, exitReasonClass } from "../utils/utils";

// ── Hero Signal Card ───────────────────────────────────────────────────────
function HeroSignal({ signal, strategy }) {
  if (!signal) return null;
  const reasons = getWhyReasons(strategy, signal);
  const isBuy   = signal.type === "BUY";

  return (
    <div className={`hero-inner ${signal.type}`}>
      <div className={`hero-type ${signal.type}`}>
        {isBuy ? "▲ BUY SIGNAL" : "▼ SELL SIGNAL"}
      </div>
      <div className="hero-grid">
        <div className="hc"><div className="lbl">Entry</div><div className="val entry">{fmt(signal.price)}</div></div>
        <div className="hc"><div className="lbl">Stop Loss</div><div className="val sl">{fmt(signal.sl)}</div></div>
        <div className="hc"><div className="lbl">Target</div><div className="val tp">{fmt(signal.tp)}</div></div>
        <div className="hc"><div className="lbl">RSI</div><div className="val">{signal.rsi}</div></div>
        <div className="hc"><div className="lbl">ATR</div><div className="val">{fmt(signal.atr)}</div></div>
        <div className="hc"><div className="lbl">R : R</div><div className="val">1 : 2</div></div>
        {signal.target_time && (
          <div className="hc target-card">
            <div className="lbl">⏱ Target Time Estimate</div>
            <div className="val target-val">{signal.target_time}</div>
            <div className="val-sub">By {signal.target_datetime} · ~{signal.target_bars} bars</div>
          </div>
        )}
      </div>
      <div className="hero-why">
        {reasons.map((r, i) => (
          <div key={i}><span className="ck">✓</span> {r}</div>
        ))}
      </div>
    </div>
  );
}

// ── Active Trade Panel ─────────────────────────────────────────────────────
function ActiveTradePanel({ trade, livePrice, livePnl, onClose }) {
  const [elapsed, setElapsed] = useState(0);
  const timerRef = useRef(null);

  useEffect(() => {
    if (!trade) return;
    const tick = () => setElapsed(elapsedMins(trade.entry_time));
    tick();
    timerRef.current = setInterval(tick, 1000);
    return () => clearInterval(timerRef.current);
  }, [trade]);

  if (!trade) return null;

  const estMin   = trade.expected_time_minutes;
  const progress = Math.min(100, (elapsed / estMin) * 100);
  const progColor = progress > 80 ? "var(--yellow)" : trade.side === "BUY" ? "var(--green)" : "var(--red)";

  // BUG FIX: was `el.className = 'profit' ? ... : 'loss'` — always truthy
  const pnlClass = livePnl != null ? (livePnl >= 0 ? "profit" : "loss") : "";
  const pnlSign  = livePnl != null && livePnl >= 0 ? "+" : "";

  return (
    <div className={`trade-panel ${trade.side}`}>
      <div className={`trade-badge ${trade.side}`}>
        {trade.side === "BUY" ? "▲ LONG" : "▼ SHORT"} ACTIVE
      </div>
      <div className="trade-pnl-row">
        <span className="trade-pnl-lbl">Live P&amp;L</span>
        <span className={`trade-pnl-val ${pnlClass}`}>
          {livePnl != null ? `${pnlSign}${fmt(livePnl)}` : "—"}
        </span>
      </div>
      <div className="trade-grid">
        <div className="tc"><div className="lbl">Entry</div><div className="val">{fmt(trade.entry_price)}</div></div>
        <div className="tc"><div className="lbl">Current</div><div className="val">{fmt(livePrice)}</div></div>
        <div className="tc"><div className="lbl">Target</div><div className="val tp">{fmt(trade.target_price)}</div></div>
        <div className="tc"><div className="lbl">Stop Loss</div><div className="val sl">{fmt(trade.stop_loss)}</div></div>
        <div className="tc"><div className="lbl">Strategy</div><div className="val">{trade.strategy || "—"}</div></div>
        <div className="tc"><div className="lbl">Confidence</div><div className="val">{trade.confidence}%</div></div>
      </div>
      <div className="progress-wrap">
        <div className="progress-bar" style={{ width: `${progress}%`, background: progColor }} />
      </div>
      <div className="trade-elapsed">
        ⏱ Elapsed: <b>{elapsed}m</b> · Est: <b>{Math.round(estMin)}m</b>
      </div>
      <button className="trade-close-btn" onClick={onClose}>✕ Close Trade Now</button>
    </div>
  );
}

// ── Exit Banner ────────────────────────────────────────────────────────────
function ExitBanner({ exit, onDismiss }) {
  if (!exit) return null;

  // BUG FIX: was `'var(--red')` — unmatched quote in template literal
  const isProfit  = exit.pnl >= 0;
  const pnlSign   = isProfit ? "+" : "";
  const reasonCls = exitReasonClass(exit.exit_reason);

  return (
    <div className={`exit-banner ${isProfit ? "profit" : "loss"}`}>
      <div className={`exit-title ${isProfit ? "profit" : "loss"}`}>
        {isProfit ? "✅ Trade Profitable!" : "❌ Trade Closed at Loss"}
      </div>
      <div className={`exit-reason-badge ${reasonCls}`}>{exit.exit_reason}</div>
      <div className="exit-grid">
        <div className="ec"><div className="lbl">Entry</div><div className="val">{fmt(exit.entry_price)}</div></div>
        <div className="ec"><div className="lbl">Exit Price</div><div className="val">{fmt(exit.exit_price)}</div></div>
        <div className="ec">
          <div className="lbl">P&amp;L</div>
          <div className="val" style={{ color: isProfit ? "var(--green)" : "var(--red)" }}>
            {pnlSign}{fmt(exit.pnl)} ({pnlSign}{exit.pnl_pct}%)
          </div>
        </div>
        <div className="ec"><div className="lbl">Duration</div><div className="val">{Math.round(exit.duration_minutes)}m</div></div>
      </div>
      <button className="exit-dismiss" onClick={onDismiss}>↩ Dismiss — Ready for next signal</button>
    </div>
  );
}

// ── Risk Calculator ────────────────────────────────────────────────────────
function RiskCalculator({ defaultEntry, defaultSL }) {
  const [capital, setCapital] = useState(100000);
  const [riskPct, setRiskPct] = useState(1);
  const [entry,   setEntry]   = useState(defaultEntry || "");
  const [sl,      setSL]      = useState(defaultSL || "");
  const [result,  setResult]  = useState(null);

  useEffect(() => { if (defaultEntry) setEntry(defaultEntry); }, [defaultEntry]);
  useEffect(() => { if (defaultSL)    setSL(defaultSL); },    [defaultSL]);

  const calc = () => {
    const cap     = parseFloat(capital) || 0;
    const rp      = parseFloat(riskPct) || 1;
    const ent     = parseFloat(entry)   || 0;
    const stopLoss = parseFloat(sl)     || 0;
    if (!ent || !stopLoss || ent === stopLoss) return;
    const riskAmt  = cap * (rp / 100);
    const perUnit  = Math.abs(ent - stopLoss);
    const qty      = Math.max(1, Math.floor(riskAmt / perUnit));
    setResult({ qty, riskAmt, totalVal: qty * ent, perUnit });
  };

  return (
    <div className="risk-section">
      <div className="p-title">🧮 Risk Calculator</div>
      <div className="r-grid">
        <div className="ig"><label>Capital</label><input type="number" value={capital} onChange={(e) => setCapital(e.target.value)} /></div>
        <div className="ig"><label>Risk %</label><input type="number" value={riskPct} step="0.1" onChange={(e) => setRiskPct(e.target.value)} /></div>
        <div className="ig"><label>Entry</label><input type="number" value={entry} placeholder="262.50" onChange={(e) => setEntry(e.target.value)} /></div>
        <div className="ig"><label>Stop Loss</label><input type="number" value={sl} placeholder="258.00" onChange={(e) => setSL(e.target.value)} /></div>
      </div>
      <button className="calc-btn" onClick={calc}>Calculate Position Size</button>
      {result && (
        <div className="risk-res">
          <div className="rr"><span>Qty</span><span className="rv">{result.qty} units</span></div>
          <div className="rr"><span>Risk Amount</span><span className="rv">₹{result.riskAmt.toFixed(2)}</span></div>
          <div className="rr"><span>Total Value</span><span className="rv">₹{result.totalVal.toFixed(2)}</span></div>
          <div className="rr"><span>Risk / Unit</span><span className="rv">₹{result.perUnit.toFixed(2)}</span></div>
        </div>
      )}
    </div>
  );
}

// ── Signal History Card ────────────────────────────────────────────────────
function SignalHistoryCard({ sig, label }) {
  const isBuy = sig.type === "BUY" || sig.signal_type === "BUY";
  return (
    <div className={`sig-card ${isBuy ? "BUY" : "SELL"}`}>
      <div className="sig-row">
        <b>{sig.symbol || label}</b>
        <b style={{ color: isBuy ? "var(--green)" : "var(--red)" }}>
          {isBuy ? "▲" : "▼"} {isBuy ? "BUY" : "SELL"}
        </b>
      </div>
      <div className="sig-row"><span>Entry</span><span className="v entry">{fmt(sig.price)}</span></div>
      <div className="sig-row">
        <span>SL / TP</span>
        <span className="v">{fmt(sig.sl)} / <span style={{ color: "var(--green)" }}>{fmt(sig.tp)}</span></span>
      </div>
      {sig.target_time && (
        <div className="sig-row"><span>⏱ Target</span><span className="v" style={{ color: "var(--yellow)" }}>{sig.target_time}</span></div>
      )}
      <div className="sig-ts">{sig.ts || ""}</div>
    </div>
  );
}

// ── Main SignalTab ─────────────────────────────────────────────────────────
export default function SignalTab({ symbol, interval }) {
  const { lastSignal }                      = useWebSocket();
  const { activeTrade, livePrice, livePnl,
          lastExitEv, dismissExit, forceClose } = useTrade();
  const { data }                            = useChartData(symbol.yahoo, interval, "pro_mtf");
  const [heroSignal,  setHeroSignal]        = useState(null);
  const [sigHistory,  setSigHistory]        = useState([]);
  const [strategy,    setStrategy]          = useState("pro_mtf");
  const seededSymRef = useRef(null);  // track which symbol's history we've seeded

  // Seed hero signal + history from chart data whenever symbol/interval loads
  useEffect(() => {
    if (!data) return;
    const key = `${symbol.yahoo}__${interval}`;
    if (seededSymRef.current === key) return; // don't re-seed on minor re-renders
    seededSymRef.current = key;

    // Build history from all historical chart signals (most recent first, max 60)
    if (data.signals?.length) {
      const historical = [...data.signals]
        .reverse()
        .slice(0, 60)
        .map((s) => ({
          ...s,
          symbol: symbol.label,
          // Normalise type field — chart signals use `type`, WS signals use `signal_type`
          type:   s.signal_type || s.type,
          ts:     "", // historical — no local timestamp
        }));
      setSigHistory(historical);
    }

    if (data.latest_signal) {
      setHeroSignal({ ...data.latest_signal, symbol: symbol.label });
      setStrategy(data.latest_signal.strategy || "pro_mtf");
    }
  }, [data, symbol.yahoo, symbol.label, interval]);

  // Push live WS signal to top of history
  useEffect(() => {
    if (!lastSignal) return;
    const enriched = {
      ...lastSignal,
      // BUG FIX: WS sends `signal_type` for BUY/SELL direction, not `type`
      type: lastSignal.signal_type || lastSignal.type_,
      ts:   new Date().toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }),
    };
    setHeroSignal(enriched);
    setSigHistory((prev) => [enriched, ...prev].slice(0, 60));
    // Browser notification
    if (Notification.permission === "granted") {
      new Notification(`${enriched.type} — ${enriched.symbol || symbol.label}`, {
        body: `Entry: ${fmt(enriched.price)}  SL: ${fmt(enriched.sl)}  TP: ${fmt(enriched.tp)}`,
      });
    }
  }, [lastSignal]);

  // Reset when symbol changes so stale data from previous symbol is cleared
  useEffect(() => {
    setHeroSignal(null);
    setSigHistory([]);
  }, [symbol.yahoo]);

  const handleClose = async () => {
    await forceClose(symbol.yahoo, livePrice || 0);
  };

  const showNothing = !heroSignal && !activeTrade && !lastExitEv;

  return (
    <div className="sig-tab">
      <div className="sig-panel">
        <div className="p-title">Latest Signal</div>

        {heroSignal && !activeTrade && !lastExitEv && (
          <HeroSignal signal={heroSignal} strategy={strategy} />
        )}

        <ActiveTradePanel
          trade={activeTrade}
          livePrice={livePrice}
          livePnl={livePnl}
          onClose={handleClose}
        />

        <ExitBanner exit={lastExitEv} onDismiss={dismissExit} />

        {showNothing && (
          <div className="no-signal">
            <div className="ns-icon">📡</div>
            Select a symbol from the watchlist<br />or scan one above
          </div>
        )}

        <div className="p-title" style={{ marginTop: 8 }}>
          Signal History {sigHistory.length > 0 && `(${sigHistory.length})`}
        </div>
        {sigHistory.length === 0 && (
          <div className="no-signal" style={{ padding: "12px 0", fontSize: 12 }}>
            No signals yet for this symbol / timeframe
          </div>
        )}
        {sigHistory.map((s, i) => (
          <SignalHistoryCard key={i} sig={s} label={symbol.label} />
        ))}
      </div>

      <RiskCalculator
        defaultEntry={heroSignal?.price}
        defaultSL={heroSignal?.sl}
      />
    </div>
  );
}
