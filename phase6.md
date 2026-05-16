# Phase 6 — React.js Dashboard & Interactive Charting

> **Goal:** Build a production-grade React.js frontend that serves as the command center for TradeOS. It connects to the FastAPI backend and displays real-time leaderboards, interactive candlestick charts with buy/sell markers, live positions, trade history, AI reasoning logs, and risk status — all separated per AI agent.

---

## 6.1 Architecture Overview

```
  React.js Frontend (Vite)
  ────────────────────────
  │
  ├── Pages
  │   ├── Dashboard (Home)        → Leaderboard + Summary
  │   ├── Agent Detail            → Per-AI deep dive
  │   ├── Trade History           → Full trade log with filters
  │   ├── Live Positions          → Open positions across all AIs
  │   ├── Market Overview         → Watchlist + Indices
  │   └── Settings                → Config management
  │
  ├── Components
  │   ├── Leaderboard             → Ranked AI performance table
  │   ├── CandlestickChart        → TradingView Lightweight Charts
  │   ├── TradeMarkers            → Buy/Sell points on chart
  │   ├── EquityCurve             → PnL over time line chart
  │   ├── PositionCard            → Open position details
  │   ├── TradeRow                → Single trade in history
  │   ├── AIReasoningCard         → AI decision + reasoning
  │   ├── RiskStatusBadge         → Circuit breaker status
  │   └── MarketHeatmap           → Watchlist performance grid
  │
  └── Services
      └── api.js                  → Axios/fetch wrappers for backend
```

---

## 6.2 Project Initialization

### Step 1: Create Vite React App

```bash
cd TradeOS/frontend
npx -y create-vite@latest ./ --template react
npm install
```

### Step 2: Install Dependencies

```bash
# Charting
npm install lightweight-charts

# Data fetching
npm install axios

# Routing
npm install react-router-dom

# Date formatting
npm install date-fns

# Icons
npm install lucide-react

# Notifications
npm install react-hot-toast
```

---

## 6.3 Design System

### 6.3.1 Color Palette — Dark Trading Terminal Theme

```css
/* index.css — Global Design Tokens */

:root {
    /* Background layers */
    --bg-primary: #0a0e17;          /* Deepest background */
    --bg-secondary: #111827;        /* Card backgrounds */
    --bg-tertiary: #1a2332;         /* Elevated surfaces */
    --bg-hover: #1f2b3d;            /* Hover states */

    /* Text */
    --text-primary: #e2e8f0;
    --text-secondary: #94a3b8;
    --text-muted: #64748b;

    /* Trading colors */
    --green-profit: #22c55e;        /* Profit / Buy / Bullish */
    --green-glow: rgba(34, 197, 94, 0.15);
    --red-loss: #ef4444;            /* Loss / Sell / Bearish */
    --red-glow: rgba(239, 68, 68, 0.15);

    /* Agent brand colors */
    --color-chatgpt: #10a37f;       /* OpenAI green */
    --color-gemini: #4285f4;        /* Google blue */
    --color-claude: #d97706;        /* Anthropic amber */
    --color-grok: #a855f7;          /* xAI purple */

    /* Accent */
    --accent-blue: #3b82f6;
    --accent-cyan: #06b6d4;

    /* Borders */
    --border-color: #1e293b;
    --border-glow: rgba(59, 130, 246, 0.3);

    /* Fonts */
    --font-mono: 'JetBrains Mono', 'Fira Code', monospace;
    --font-sans: 'Inter', -apple-system, sans-serif;

    /* Radius */
    --radius-sm: 6px;
    --radius-md: 10px;
    --radius-lg: 16px;

    /* Shadows */
    --shadow-card: 0 4px 24px rgba(0, 0, 0, 0.4);
    --shadow-glow-green: 0 0 20px rgba(34, 197, 94, 0.2);
    --shadow-glow-red: 0 0 20px rgba(239, 68, 68, 0.2);
}

/* Google Font Import */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: var(--font-sans);
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
}
```

### 6.3.2 Glassmorphism Card Component

```css
.card {
    background: linear-gradient(135deg, rgba(17, 24, 39, 0.8), rgba(26, 35, 50, 0.6));
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: 24px;
    backdrop-filter: blur(12px);
    box-shadow: var(--shadow-card);
    transition: all 0.3s ease;
}

.card:hover {
    border-color: var(--border-glow);
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}
```

---

## 6.4 Page Designs

### 6.4.1 Dashboard (Home Page)

The main command center. Shows everything at a glance.

**Layout:**

```
┌──────────────────────────────────────────────────────────────┐
│  HEADER: TradeOS Logo | Market Status (Open/Closed) | Clock │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐       │
│  │ Nifty 50 │ │  Sensex  │ │India VIX │ │  Active  │       │
│  │ 24,500   │ │ 80,200   │ │  14.2    │ │ Trades:8 │       │
│  │  +0.45%  │ │  +0.38%  │ │   Low    │ │          │       │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘       │
│                                                              │
│  ┌──────────────────────────────────────────────────┐       │
│  │              AI LEADERBOARD                       │       │
│  │                                                   │       │
│  │  Rank │ Agent    │ Capital    │ PnL     │ Win%    │       │
│  │  🥇   │ Gemini   │ ₹1,08,500 │ +₹8,500 │ 68%    │       │
│  │  🥈   │ ChatGPT  │ ₹1,05,200 │ +₹5,200 │ 62%    │       │
│  │  🥉   │ Claude   │ ₹1,02,100 │ +₹2,100 │ 55%    │       │
│  │  4    │ Grok     │ ₹99,800   │ -₹200   │ 48%    │       │
│  └──────────────────────────────────────────────────┘       │
│                                                              │
│  ┌──────────────────────┐ ┌──────────────────────────┐      │
│  │   Equity Curves      │ │    Live Positions         │      │
│  │   (overlaid for all  │ │    (cards for each open   │      │
│  │    4 AIs on one      │ │     position by agent)    │      │
│  │    chart)            │ │                           │      │
│  └──────────────────────┘ └──────────────────────────┘      │
│                                                              │
│  ┌──────────────────────────────────────────────────┐       │
│  │          Recent Trades (Last 10)                  │       │
│  │  Agent   │ Symbol  │ Action │ PnL    │ Time      │       │
│  │  ChatGPT │ INFY.NS │ SELL   │ +₹500  │ 10:30 AM  │       │
│  │  Grok    │ BEL.NS  │ BUY   │ open   │ 10:15 AM  │       │
│  └──────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────┘
```

### 6.4.2 Agent Detail Page — `/agent/:agentId`

Deep dive into a single AI's performance with interactive charts.

**Key Sections:**

1. **Agent Header** — Name, model, total PnL, win rate, capital, risk status badge
2. **Candlestick Chart with Trade Markers** — The MOST IMPORTANT visual component:
   - Full interactive candlestick chart (using TradingView Lightweight Charts)
   - Stock selector dropdown to view chart for any traded stock
   - **Green triangle markers** on the chart at exact price where the AI bought
   - **Red triangle markers** on the chart at exact price where the AI sold
   - Hovering a marker shows: quantity, PnL, confidence, reasoning
   - Stop-loss and target lines drawn as horizontal dashed lines
3. **Open Positions Table** — Current holdings with live PnL
4. **Trade History Table** — Full sortable/filterable trade log
5. **AI Reasoning Log** — Raw AI decisions with input payload and output
6. **Personality Metrics** — Aggressiveness, avg confidence, risk tolerance, etc.
7. **Daily Performance Chart** — Bar chart of daily PnL

### 6.4.3 Candlestick Chart Implementation

```javascript
// components/CandlestickChart.jsx

import { createChart } from 'lightweight-charts';
import { useEffect, useRef } from 'react';

/**
 * Creates a professional trading chart with:
 * 1. Candlestick series (OHLCV data)
 * 2. Volume histogram below
 * 3. EMA overlays (20, 50)
 * 4. Trade markers (buy/sell points)
 *
 * Trade Markers:
 * - BUY markers: Green upward triangle at entry_price, placed at entry_time
 * - SELL markers: Red downward triangle at exit_price, placed at exit_time
 * - SL_HIT markers: Red X marker
 * - TARGET_HIT markers: Green checkmark
 *
 * Each marker has a tooltip showing:
 * - Agent name
 * - Action (BUY/SELL)
 * - Price
 * - Quantity
 * - PnL (if closed)
 * - Confidence
 * - Reasoning (truncated)
 */

export default function CandlestickChart({ symbol, candles, trades, agentId }) {
    const chartContainerRef = useRef(null);

    useEffect(() => {
        const chart = createChart(chartContainerRef.current, {
            width: chartContainerRef.current.clientWidth,
            height: 500,
            layout: {
                background: { color: '#0a0e17' },
                textColor: '#94a3b8',
                fontSize: 12,
                fontFamily: "'Inter', sans-serif",
            },
            grid: {
                vertLines: { color: 'rgba(30, 41, 59, 0.5)' },
                horzLines: { color: 'rgba(30, 41, 59, 0.5)' },
            },
            crosshair: {
                mode: 0, // Normal crosshair
                vertLine: { color: 'rgba(59, 130, 246, 0.4)' },
                horzLine: { color: 'rgba(59, 130, 246, 0.4)' },
            },
            timeScale: {
                borderColor: '#1e293b',
                timeVisible: true,
                secondsVisible: false,
            },
            rightPriceScale: {
                borderColor: '#1e293b',
            },
        });

        // Candlestick series
        const candleSeries = chart.addCandlestickSeries({
            upColor: '#22c55e',
            downColor: '#ef4444',
            borderDownColor: '#ef4444',
            borderUpColor: '#22c55e',
            wickDownColor: '#ef4444',
            wickUpColor: '#22c55e',
        });
        candleSeries.setData(candles);

        // Volume histogram
        const volumeSeries = chart.addHistogramSeries({
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume',
        });
        // ... set volume data

        // Trade markers
        const markers = trades.map(trade => ({
            time: trade.entry_time,
            position: trade.action === 'BUY' ? 'belowBar' : 'aboveBar',
            color: trade.action === 'BUY' ? '#22c55e' : '#ef4444',
            shape: trade.action === 'BUY' ? 'arrowUp' : 'arrowDown',
            text: `${trade.action} @ ₹${trade.entry_price}`,
        }));
        candleSeries.setMarkers(markers);

        return () => chart.remove();
    }, [candles, trades]);

    return <div ref={chartContainerRef} style={{ width: '100%' }} />;
}
```

### 6.4.4 Trade History Page

```
┌──────────────────────────────────────────────────────────────┐
│  FILTERS: [All Agents ▾] [All Symbols ▾] [All Status ▾]    │
│           [Date Range] [Search...]                           │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  Agent   │ Symbol      │ Type     │ Action │ Entry  │ Exit   │
│  ────────┼─────────────┼──────────┼────────┼────────┼────────│
│  🟢 GPT  │ RELIANCE.NS │ INTRADAY │ BUY    │ ₹2,891 │ ₹2,975 │
│          │             │          │        │        │        │
│  PnL: +₹420 │ Status: TARGET_HIT │ Confidence: 81 │ Duration: 2h 15m
│  Reasoning: "Strong breakout with volume confirmation above VWAP..."
│                                                              │
│  🔴 Grok │ INFY.NS     │ INTRADAY │ SHORT  │ ₹1,480 │ ₹1,492 │
│          │             │          │        │        │        │
│  PnL: -₹240 │ Status: SL_HIT │ Confidence: 65 │ Duration: 45m
│  Reasoning: "Bearish breakdown below support with negative news..."
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### 6.4.5 Market Overview Page

```
┌──────────────────────────────────────────────────────────────┐
│  MARKET HEATMAP                                              │
│                                                              │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐   │
│  │ RELIANCE  │ │   TCS     │ │  INFY     │ │ HDFCBANK  │   │
│  │ ₹2,890    │ │ ₹3,450    │ │ ₹1,480    │ │ ₹1,650    │   │
│  │  +1.2%    │ │  -0.5%    │ │  +0.8%    │ │  +0.3%    │   │
│  │  🟢       │ │  🔴       │ │  🟢       │ │  🟢       │   │
│  └───────────┘ └───────────┘ └───────────┘ └───────────┘   │
│  (Color intensity based on % change)                         │
│                                                              │
│  ┌──────────────────────────────────────────────────┐       │
│  │  LATEST NEWS FEED                                 │       │
│  │  🟢 Reliance Q4 profit surges 12% — Google News   │       │
│  │  🔴 IT sector faces margin pressure — ET Markets   │       │
│  │  ⚪ RBI keeps repo rate unchanged — NewsAPI        │       │
│  └──────────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────────┘
```

---

## 6.5 API Service Layer

```javascript
// services/api.js

import axios from 'axios';

const API_BASE = 'http://localhost:8000/api';

const api = axios.create({
    baseURL: API_BASE,
    timeout: 10000,
});

export const marketAPI = {
    getIndices: () => api.get('/market/indices'),
    getPrice: (symbol) => api.get(`/market/price/${symbol}`),
    getCandles: (symbol) => api.get(`/market/candles/${symbol}`),
    getNews: (symbol) => api.get(`/market/news/${symbol}`),
    getWatchlist: () => api.get('/market/watchlist'),
};

export const agentAPI = {
    getAll: () => api.get('/agents'),
    getById: (id) => api.get(`/agents/${id}`),
    getDecisions: (id) => api.get(`/agents/${id}/decisions`),
    getPersonality: (id) => api.get(`/agents/${id}/personality`),
    getCompare: () => api.get('/agents/compare'),
};

export const tradeAPI = {
    getAll: (params) => api.get('/trades', { params }),
    getByAgent: (agentId) => api.get(`/trades/${agentId}`),
    getDetail: (tradeId) => api.get(`/trades/${tradeId}/detail`),
};

export const positionAPI = {
    getAll: () => api.get('/positions'),
    getByAgent: (agentId) => api.get(`/positions/${agentId}`),
};

export const performanceAPI = {
    getDaily: () => api.get('/performance/daily'),
    getEquity: (agentId) => api.get(`/performance/${agentId}/equity`),
    getRiskStatus: () => api.get('/risk/status'),
};
```

---

## 6.6 Real-Time Updates

### Polling Strategy

```javascript
// hooks/usePolling.js

import { useState, useEffect } from 'react';

/**
 * Polls the backend at a set interval for live data updates.
 *
 * During market hours (9:15 AM - 3:30 PM IST):
 *   - Positions & prices: every 10 seconds
 *   - Leaderboard: every 30 seconds
 *   - Trade history: every 60 seconds
 *
 * Outside market hours:
 *   - All data: every 5 minutes (minimal polling)
 */
export function usePolling(fetchFn, intervalMs = 10000) {
    const [data, setData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const poll = async () => {
            try {
                const result = await fetchFn();
                setData(result.data);
                setLoading(false);
            } catch (err) {
                console.error('Polling error:', err);
            }
        };

        poll(); // Initial fetch
        const interval = setInterval(poll, intervalMs);
        return () => clearInterval(interval);
    }, [fetchFn, intervalMs]);

    return { data, loading };
}
```

---

## 6.7 Responsive Layout

```css
/* Responsive grid for dashboard cards */
.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 20px;
    padding: 24px;
}

@media (max-width: 1200px) {
    .dashboard-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 768px) {
    .dashboard-grid { grid-template-columns: 1fr; }
}

/* Sidebar navigation */
.sidebar {
    width: 260px;
    height: 100vh;
    position: fixed;
    background: var(--bg-secondary);
    border-right: 1px solid var(--border-color);
    padding: 24px 16px;
}

.main-content {
    margin-left: 260px;
    padding: 24px;
    min-height: 100vh;
}
```

---

## 6.8 Phase 6 Completion Checklist

| #  | Task                                              | Status |
|----|---------------------------------------------------|--------|
| 1  | Initialize Vite React project                     | ☐     |
| 2  | Install all npm dependencies                       | ☐     |
| 3  | Create global CSS design system (dark theme)       | ☐     |
| 4  | Build sidebar navigation with React Router         | ☐     |
| 5  | Build Dashboard page (leaderboard + summary cards) | ☐     |
| 6  | Build Leaderboard component with agent colors      | ☐     |
| 7  | Build CandlestickChart with Lightweight Charts     | ☐     |
| 8  | Add trade markers (buy/sell) on candlestick chart  | ☐     |
| 9  | Build Agent Detail page with all sections          | ☐     |
| 10 | Build Trade History page with filters              | ☐     |
| 11 | Build Live Positions page with real-time PnL       | ☐     |
| 12 | Build Market Overview page with heatmap            | ☐     |
| 13 | Build Equity Curve chart (all 4 AIs overlaid)      | ☐     |
| 14 | Implement API service layer (api.js)               | ☐     |
| 15 | Implement polling for real-time updates             | ☐     |
| 16 | Implement responsive layout for all screen sizes   | ☐     |
| 17 | Test full frontend ↔ backend integration           | ☐     |

---

> **Phase 6 is COMPLETE when:** The React dashboard renders all pages, fetches live data from the FastAPI backend, displays interactive candlestick charts with buy/sell markers for each AI, shows the leaderboard, live positions with floating PnL, and trade history with AI reasoning.

> **Next →** [Phase 7: Automation, Scheduling & 30-Day Live Simulation](./phase7.md)
