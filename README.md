# 🚀 Pro Trading Terminal — v3 React Edition

Full SOLID backend (v2) + React frontend with component-level Single Responsibility.

---

## What Changed (v2 → v3)

| v2 (SOLID Backend)              | v3 (React Frontend)                                      |
|---|---|
| `frontend/index.html` — 900 lines monolith | 12 focused React components                |
| Global JS variables for state   | `WebSocketContext` + `TradeContext` providers             |
| `fetch()` scattered everywhere  | `services/api.js` — single API abstraction layer         |
| String template literal bugs    | Type-safe JSX with no concatenation bugs                 |
| WS `type` field collision bug   | Fixed: `signal_type` for BUY/SELL, `type` for WS msgs   |
| PnL class always "profit" bug   | Fixed: proper ternary `pnl >= 0 ? "profit" : "loss"`    |
| Inline `getWhyReasons` strings  | `utils/getWhyReasons()` — pure utility function          |

---

## File Structure

```
├── main.py                          ← Composition root (unchanged API)
├── requirements.txt
├── watchlist.json
│
├── backend/                         ← Unchanged SOLID backend (v2)
│   ├── interfaces/
│   ├── indicators/
│   ├── strategies/
│   ├── services/
│   ├── repositories/
│   └── utils/
│
└── frontend/                        ← React + Vite frontend
    ├── index.html                   ← Vite HTML template
    ├── vite.config.js               ← Dev proxy → :8000
    ├── package.json
    └── src/
        ├── main.jsx                 ← React entry point
        ├── App.jsx                  ← Composition root (mirrors main.py's role)
        ├── index.css                ← All styles (CSS variables, no CSS-in-JS)
        │
        ├── context/
        │   ├── WebSocketContext.jsx ← SR: WS lifecycle + message dispatch
        │   └── TradeContext.jsx     ← SR: active trade state + exit events
        │
        ├── hooks/
        │   ├── useStrategies.js     ← SR: fetch strategy list
        │   ├── useWatchlist.js      ← SR: watchlist CRUD + signal badges
        │   └── useChartData.js      ← SR: fetch chart data with abort
        │
        ├── services/
        │   └── api.js               ← SR: ALL HTTP calls (DIP — components depend on this)
        │
        ├── utils/
        │   └── utils.js             ← Pure functions: fmt, applyTZ, getWhyReasons, etc.
        │
        └── components/
            ├── TopBar.jsx           ← SR: symbol input, TF, live tick, market status
            ├── StrategyBar.jsx      ← SR: strategy selector
            ├── Watchlist.jsx        ← SR: watchlist display + signal badges
            ├── ChartPanel.jsx       ← SR: LightweightCharts bridge
            ├── Sidebar.jsx          ← SR: tab container only
            ├── SignalTab.jsx        ← SR: hero signal, trade panel, exit banner, risk calc
            ├── NewsTab.jsx          ← SR: fetch + display news
            ├── PredictTab.jsx       ← SR: display ML prediction
            └── AddSymbolModal.jsx   ← SR: watchlist add dialog
```

---

## SOLID Applied to the React Frontend

### S — Single Responsibility
Every component has one job. `Sidebar` only manages tab switching — it never
fetches data. `ChartPanel` only renders the chart — it never manages trades.
`api.js` is the only file that calls `fetch()`.

### O — Open/Closed
Adding a 4th sidebar tab requires zero changes to existing components:
```jsx
// Sidebar.jsx — add one entry:
const TABS = [..., { id: "alerts", label: "🔔 Alerts" }];
// Add one panel, create AlertsTab.jsx — done.
```

### L — Liskov Substitution
`WebSocketContext` can be swapped for a mock in tests without any component changes.
`api.js` functions can be replaced with mock versions for Storybook/testing.

### I — Interface Segregation
`useWatchlist` only exposes `{ items, signals, add, remove, setSignal }`.
`useChartData` only exposes `{ data, loading, error }`.
No component receives more than it needs.

### D — Dependency Inversion
Components import from `../services/api` and `../context/*`, never from
`fetch` or `WebSocket` directly. The concrete implementations (browser APIs)
are isolated in context providers and the api service.

---

## Bug Fixes (v2 → v3)

### 1. WS signal `type` field collision
**Before (main.py):**
```python
payload = { "type": "signal", "type_": last.type, ... }  # type_ unreliable
```
**After:**
```python
payload = { "type": "signal", "signal_type": last.type, ... }  # explicit
```
**Frontend fix (SignalTab.jsx):**
```jsx
type: lastSignal.signal_type || lastSignal.type_  // reads correct field
```

### 2. PnL class always "profit"
**Before (index.html):**
```js
el.className = 'profit' ? (pnl >= 0 ? 'profit' : 'loss') : 'loss';
// 'profit' is truthy → always 'profit'
```
**After (SignalTab.jsx):**
```jsx
const pnlClass = livePnl != null ? (livePnl >= 0 ? "profit" : "loss") : "";
```

### 3. Template literal unmatched quote in exit history
**Before (index.html):**
```js
'color:' + (ev.pnl >= 0 ? 'var(--green)' : 'var(--red')  // missing )
```
**After:** Uses JSX — no string concatenation, no quote matching bugs.

### 4. Watchlist signal badge never cleared after exit
**Before:** `wlSignals[d.symbol] = 'NONE'` only on exit WS event.
**After:** `TradeContext` listens to `lastExit` and `useWatchlist.setSignal` is
called reactively through `Watchlist.jsx` useEffect.

---

## Setup

### Backend
```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend (Development — Vite dev server with HMR)
```bash
cd frontend
npm install
npm run dev
# Open: http://localhost:5173  (proxied to :8000)
```

### Frontend (Production — serve from FastAPI)
```bash
cd frontend
npm run build          # outputs to ../frontend_dist/
cd ..
uvicorn main:app --host 0.0.0.0 --port 8000
# Open: http://localhost:8000
```

---

## Extending the Frontend

### Add a new sidebar tab
1. Create `src/components/MyTab.jsx`
2. Add `{ id: "my", label: "🔧 My Tab" }` to `TABS` in `Sidebar.jsx`
3. Add panel `<div className={...}>{activeTab === "my" && <MyTab />}</div>`

### Add a new API call
1. Add function to `src/services/api.js`
2. Call it from any component — zero other changes

### Swap WebSocket for polling
1. Implement a `PollingContext.jsx` with the same interface as `WebSocketContext`
2. Replace the import in `App.jsx` — zero component changes

---

*For educational purposes only. Not financial advice.*
