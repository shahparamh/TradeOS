import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { TrendingUp, TrendingDown, BarChart2, RefreshCw, Activity, Cpu, Search, Newspaper } from 'lucide-react';
import api, { marketAPI } from '../services/api';
import CandlestickChart from '../components/CandlestickChart';
import { NIFTY50_SYMBOLS } from '../utils/symbols';
import { toChartTime } from '../utils/chartTime';

const SENTIMENT_STYLE = {
  positive: { bg: 'var(--green-glow)', color: 'var(--green-profit)' },
  negative: { bg: 'var(--red-glow)', color: 'var(--red-loss)' },
  neutral: { bg: 'var(--bg-tertiary)', color: 'var(--text-muted)' },
};

const toChartCandles = (candles) => (candles || [])
  .map(c => ({
    time: toChartTime(c.datetime),
    open: c.open,
    high: c.high,
    low: c.low,
    close: c.close,
  }))
  .sort((a, b) => a.time - b.time);

const getHeatColor = (pct) => {
  if (pct > 3)  return { bg: 'rgba(56,217,150,0.45)',  border: 'rgba(56,217,150,0.4)' };
  if (pct > 1.5) return { bg: 'rgba(56,217,150,0.28)', border: 'rgba(56,217,150,0.25)' };
  if (pct > 0)  return { bg: 'rgba(56,217,150,0.12)',  border: 'rgba(56,217,150,0.1)' };
  if (pct > -1.5) return { bg: 'rgba(255,102,115,0.12)', border: 'rgba(255,102,115,0.1)' };
  if (pct > -3)  return { bg: 'rgba(255,102,115,0.28)', border: 'rgba(255,102,115,0.25)' };
  return { bg: 'rgba(255,102,115,0.45)', border: 'rgba(255,102,115,0.4)' };
};

const Market = () => {
  const [indices, setIndices]   = useState([]);
  const [stocks, setStocks]     = useState([]);
  const [loading, setLoading]   = useState(true);
  const [stocksLoading, setStocksLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [view, setView]         = useState('heatmap'); // 'heatmap' | 'table'

  // Charting states
  const [selectedStock, setSelectedStock] = useState(null);
  const [chartData, setChartData] = useState([]);
  const [chartLoading, setChartLoading] = useState(false);
  const [timeframe, setTimeframe] = useState('5d'); // '5d' | '1m' | '1y' | '5y'

  const handleTimeframeChange = async (tf, symbol = selectedStock) => {
    if (!symbol) return;
    setTimeframe(tf);
    setChartLoading(true);
    setChartData([]);

    let interval = '5m';
    let period = '5d';
    if (tf === '1m') { interval = '1h'; period = '1mo'; }
    else if (tf === '1y') { interval = '1d'; period = '1y'; }
    else if (tf === '5y') { interval = '1d'; period = '5y'; }

    try {
      const res = await api.get(`/market/candles/${symbol}?interval=${interval}&period=${period}`);
      const formatted = res.data.map(c => ({
        time: toChartTime(c.datetime),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close
      })).sort((a, b) => a.time - b.time);
      setChartData(formatted);
    } catch (err) {
      console.error("Failed to load chart data:", err);
    } finally {
      setChartLoading(false);
    }
  };

  const handleStockClick = async (symbol) => {
    const fullSymbol = symbol.endsWith('.NS') ? symbol : `${symbol}.NS`;
    setSelectedStock(fullSymbol);
    await handleTimeframeChange('5d', fullSymbol);
  };


  // Ad-hoc Custom AI stock analyzer states
  const [searchParams] = useSearchParams();
  const [searchTicker, setSearchTicker] = useState(searchParams.get('symbol') || '');
  const [analysisResult, setAnalysisResult] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState(null);

  const runAnalysis = useCallback(async (rawTicker) => {
    if (!rawTicker || !rawTicker.trim()) return;
    setAnalysisLoading(true);
    setAnalysisError(null);
    setAnalysisResult(null);
    try {
      const ticker = rawTicker.trim().toUpperCase();
      // This call concurrently queries every active AI provider plus fetches news/fundamentals —
      // routinely takes 40-60s, well past the default 30s client timeout.
      const res = await api.get(`/scanner/analyze/${ticker}`, { timeout: 90000 });
      if (res.data.status === 'success') {
        setAnalysisResult(res.data);
      } else {
        setAnalysisError(res.data.message || 'Analysis failed.');
      }
    } catch (err) {
      setAnalysisError(err.response?.data?.message || 'Failed to analyze ticker. Check backend connection.');
    } finally {
      setAnalysisLoading(false);
    }
  }, []);

  const handleCustomAnalysis = (e) => {
    e.preventDefault();
    runAnalysis(searchTicker);
  };

  // Deep link from the global search (?symbol=RELIANCE) — auto-runs the same analysis.
  // Re-runs on every change to the URL param, not just on mount, since navigating here
  // from the search while already on this page doesn't remount the component.
  const symbolParam = searchParams.get('symbol');
  useEffect(() => {
    if (symbolParam) {
      setSearchTicker(symbolParam);
      runAnalysis(symbolParam);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbolParam]);


  /* ---- Indices ---- */
  const fetchIndices = useCallback(async () => {
    try {
      const res = await marketAPI.getIndices();
      setIndices(res.data);
    } catch (_) {}
    finally { setLoading(false); }
  }, []);

  /* ---- Live stock prices for heatmap ---- */
  const fetchStocks = useCallback(async () => {
    setStocksLoading(true);
    try {
      const fullSymbols = NIFTY50_SYMBOLS.map(sym => `${sym}.NS`);
      const res = await marketAPI.getPrices(fullSymbols);
      const quotes = res.data;
      const data = NIFTY50_SYMBOLS
        .map(sym => {
          const q = quotes[`${sym}.NS`];
          if (!q) return null;
          return {
            symbol: sym,
            price: q.price,
            change: q.change,
            percent_change: q.percent_change,
          };
        })
        .filter(Boolean);
      setStocks(data);
    } catch (_) {
      // keep last known stocks on failure
    } finally {
      setStocksLoading(false);
      setLastRefresh(new Date());
    }
  }, []);

  useEffect(() => {
    fetchIndices();
    fetchStocks();
    const idx = setInterval(fetchIndices, 30000);
    const stk = setInterval(fetchStocks, 60000);
    return () => { clearInterval(idx); clearInterval(stk); };
  }, [fetchIndices, fetchStocks]);

  return (
    <div className="market-page animate-fade-in">
      <header className="page-header">
        <div>
          <h1>Market Overview</h1>
          <p className="subtitle">Live NSE data — indices, Nifty 50 heatmap & stock prices</p>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:12 }}>
          {lastRefresh && (
            <span style={{ fontSize:11, color:'var(--text-muted)', fontFamily:'var(--font-mono)' }}>
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          <button className="refresh-btn" onClick={() => { fetchIndices(); fetchStocks(); }}>
            <RefreshCw size={14} /> Refresh
          </button>
          <div className="market-badge">
            <div className="pulse-dot green"></div>
            NSE LIVE
          </div>
        </div>
      </header>

      {/* Index Strip */}
      <div className="indices-strip">
        {loading ? (
          <div className="indices-loading">Fetching indices…</div>
        ) : indices.map(idx => (
          <div key={idx.symbol} className="index-chip card">
            <div className="ic-name">{idx.symbol}</div>
            <div className="ic-price mono">
              {idx.price != null ? idx.price.toLocaleString('en-IN') : '—'}
            </div>
            <div className={`ic-change ${(idx.percent_change||0) >= 0 ? 'up' : 'down'}`}>
              {(idx.percent_change||0) >= 0 ? <TrendingUp size={11}/> : <TrendingDown size={11}/>}
              {(idx.percent_change||0) >= 0 ? '+' : ''}{(idx.percent_change||0).toFixed(2)}%
            </div>
          </div>
        ))}
      </div>

      {/* AI Live Inspector Panel */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="section-header" style={{ borderBottom: '1px solid var(--border-color)', paddingBottom: 10 }}>
          <h3 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--accent-blue)' }}>
            <Cpu size={15} /> Live Multi-Agent AI Ticker Inspector
          </h3>
          <span className="badge">AD-HOC FLEET QUERY</span>
        </div>

        <div style={{ padding: '12px 4px 4px' }}>
          <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 12 }}>
            Query live candles, calculate indicators, and concurrently invoke your active AI fleet for real-time trade signals. Type any stock symbol (e.g. <b>RELIANCE</b>, <b>TATASTEEL</b>, or <b>AAPL</b>).
          </p>

          <form onSubmit={handleCustomAnalysis} style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <Search size={13} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="text"
                placeholder="Enter stock ticker (e.g. ADANIENT, INFY, TCS)..."
                value={searchTicker}
                onChange={(e) => setSearchTicker(e.target.value)}
                className="mono"
                style={{
                  width: '100%',
                  padding: '8px 10px 8px 30px',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  fontSize: 13,
                  outline: 'none',
                }}
                onFocus={(e) => e.target.style.borderColor = 'var(--accent-blue)'}
                onBlur={(e) => e.target.style.borderColor = 'var(--border-color)'}
              />
            </div>
            <button
              type="submit"
              disabled={analysisLoading}
              className="btn-primary"
              style={{ padding: '0 18px', opacity: analysisLoading ? 0.7 : 1 }}
            >
              {analysisLoading ? <RefreshCw size={13} className="spin" /> : <Activity size={13} />}
              {analysisLoading ? 'Analyzing Ticker...' : 'Inspect Ticker'}
            </button>
          </form>

          {/* Loading State */}
          {analysisLoading && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '40px 0', gap: 16 }}>
              <RefreshCw size={28} className="spin" style={{ color: 'var(--accent-blue)' }} />
              <div style={{ textAlign: 'center' }}>
                <h4 style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4, fontSize: 13 }}>Invoking AI Fleet...</h4>
                <p style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                  Fetching candles, computing VWAP, RSI, MACD indicators, and consulting agents in parallel.
                </p>
              </div>
            </div>
          )}

          {/* Error State */}
          {analysisError && (
            <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.25)', borderRadius: 4, padding: '12px 16px', color: 'var(--red-loss)', fontSize: 13, display: 'flex', alignItems: 'center', gap: 8 }}>
              ⚠️ {analysisError}
            </div>
          )}

          {/* Analysis Results Display */}
          {analysisResult && (
            <div className="animate-fade-in">
              {/* Technical Indicator Summary Bar */}
              <div style={{ background: 'rgba(255, 255, 255, 0.02)', borderRadius: 4, border: '1px solid var(--border-color)', padding: '16px 20px', marginBottom: 20 }}>
                <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: 12, borderBottom: '1px solid rgba(255, 255, 255, 0.06)', paddingBottom: 12, marginBottom: 12 }}>
                  <div>
                    <h4 style={{ fontWeight: 700, fontSize: 18, color: 'var(--text-primary)', margin: 0 }}>
                      {analysisResult.symbol}
                    </h4>
                    <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>LIVE ANALYSIS SNAPSHOT</span>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                      ₹{analysisResult.price?.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </div>
                    <span className="badge" style={{
                      background: analysisResult.technical_summary?.trend?.includes('bullish') ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                      color: analysisResult.technical_summary?.trend?.includes('bullish') ? 'var(--green-profit)' : 'var(--red-loss)',
                      fontSize: 10,
                      fontWeight: 700
                    }}>
                      {analysisResult.technical_summary?.trend?.toUpperCase().replace('_', ' ')}
                    </span>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 16 }}>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>RSI (14)</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                      {analysisResult.technical_summary?.rsi?.toFixed(1)} 
                      <span style={{ fontSize: 10, marginLeft: 4, color: analysisResult.technical_summary?.rsi < 35 ? 'var(--green-profit)' : analysisResult.technical_summary?.rsi > 65 ? 'var(--red-loss)' : 'var(--text-muted)' }}>
                        ({analysisResult.technical_summary?.rsi < 35 ? 'Oversold' : analysisResult.technical_summary?.rsi > 65 ? 'Overbought' : 'Neutral'})
                      </span>
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>MACD Signal</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                      {analysisResult.technical_summary?.macd?.toUpperCase()}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>VWAP Position</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                      {analysisResult.technical_summary?.price_vs_vwap?.toUpperCase()}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Bollinger Bands</div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
                      {analysisResult.technical_summary?.bb_position?.toUpperCase()}
                    </div>
                  </div>
                </div>
              </div>

              {/* Chart Analysis */}
              {analysisResult.candles?.length > 0 && (
                <div style={{ background: 'rgba(255, 255, 255, 0.02)', borderRadius: 4, border: '1px solid var(--border-color)', padding: '16px 20px', marginBottom: 20 }}>
                  <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5, margin: '0 0 12px 0' }}>
                    Chart Analysis — 5-Minute Candles (Last 5 Days)
                  </h4>
                  <CandlestickChart data={toChartCandles(analysisResult.candles)} height={280} />
                </div>
              )}

              {/* News Analysis */}
              <div style={{ background: 'rgba(255, 255, 255, 0.02)', borderRadius: 4, border: '1px solid var(--border-color)', padding: '16px 20px', marginBottom: 20 }}>
                <h4 style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: 0.5, margin: '0 0 12px 0', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <Newspaper size={13} /> News Analysis
                </h4>
                {(!analysisResult.news || analysisResult.news.length === 0) ? (
                  <p style={{ fontSize: 12, color: 'var(--text-muted)', margin: 0 }}>No recent news found for this symbol.</p>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {analysisResult.news.map((n, i) => {
                      const style = SENTIMENT_STYLE[n.sentiment] || SENTIMENT_STYLE.neutral;
                      return (
                        <a
                          key={i}
                          href={n.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, textDecoration: 'none', padding: '8px 10px', borderRadius: 6, background: 'rgba(255,255,255,0.015)' }}
                        >
                          <span style={{ fontSize: 12, color: 'var(--text-secondary)', flex: 1 }}>{n.headline}</span>
                          <span style={{ fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 4, background: style.bg, color: style.color, textTransform: 'uppercase', whiteSpace: 'nowrap' }}>
                            {n.sentiment}
                          </span>
                        </a>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Agent Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
                {analysisResult.ai_decisions.map((dec) => {
                  const isBuy = dec.decision === 'BUY';
                  const isShort = dec.decision === 'SHORT';
                  
                  // Setup brand color
                  let brandColor = 'var(--accent-blue)';
                  if (dec.agent?.toLowerCase().includes('gemini')) brandColor = 'var(--color-gemini)';
                  else if (dec.agent?.toLowerCase().includes('groq')) brandColor = 'var(--color-groq)';
                  else if (dec.agent?.toLowerCase().includes('qwen')) brandColor = 'var(--accent-cyan)';
                  else if (dec.agent?.toLowerCase().includes('deepseek')) brandColor = 'var(--color-github)';
                  else if (dec.agent?.toLowerCase().includes('ollama') || dec.agent?.toLowerCase().includes('local')) brandColor = 'var(--green-profit)';


                  return (
                    <div key={dec.agent} className="card" style={{ borderTop: `4px solid ${brandColor}`, background: 'rgba(255,255,255,0.015)', display: 'flex', flexDirection: 'column', height: '100%' }}>
                      <div style={{ padding: '14px 16px', borderBottom: '1px solid rgba(255, 255, 255, 0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 700, color: brandColor, fontSize: 14 }}>{dec.agent}</span>
                        <span className="badge" style={{
                          background: isBuy ? 'rgba(34,197,94,0.15)' : isShort ? 'rgba(239,68,68,0.15)' : 'rgba(255,255,255,0.08)',
                          color: isBuy ? 'var(--green-profit)' : isShort ? 'var(--red-loss)' : 'var(--text-muted)',
                          fontWeight: 800,
                          fontSize: 10
                        }}>
                          {dec.decision}
                        </span>
                      </div>
                      
                      <div style={{ padding: '14px 16px', flex: 1, display: 'flex', flexDirection: 'column' }}>
                        {/* Confidence indicator */}
                        <div style={{ marginBottom: 12 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
                            <span>Confidence</span>
                            <span>{dec.confidence}%</span>
                          </div>
                          <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
                            <div style={{ width: `${dec.confidence}%`, height: '100%', background: brandColor }} />
                          </div>
                        </div>

                        {/* SL / TP targets */}
                        {(isBuy || isShort) && (
                          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, background: 'rgba(255,255,255,0.02)', padding: 8, borderRadius: 6, marginBottom: 12, border: '1px solid rgba(255,255,255,0.03)' }}>
                            <div>
                              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>STOP LOSS</div>
                              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                                ₹{dec.stop_loss ? dec.stop_loss.toLocaleString('en-IN') : '—'}
                              </div>
                            </div>
                            <div>
                              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>TARGET</div>
                              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                                ₹{dec.target ? dec.target.toLocaleString('en-IN') : '—'}
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Reasoning */}
                        <div style={{ flex: 1 }}>
                          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>AI REASONING</div>
                          <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5, margin: 0, fontStyle: dec.reasoning?.includes('API error') ? 'italic' : 'normal' }}>
                            {dec.reasoning}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* View Toggle */}
      <div style={{ display:'flex', gap:8, marginBottom:20 }}>
        <button className={`filter-tab ${view==='heatmap'?'active':''}`} onClick={()=>setView('heatmap')}>
          <BarChart2 size={13}/> Heatmap
        </button>
        <button className={`filter-tab ${view==='table'?'active':''}`} onClick={()=>setView('table')}>
          <Activity size={13}/> Table View
        </button>
      </div>

      {/* Heatmap */}
      {view === 'heatmap' && (
        <div className="card heatmap-card">
          <div className="section-header">
            <h3 className="section-title"><BarChart2 size={17}/> Nifty 50 Heatmap</h3>
            <span className="badge">LIVE PRICES</span>
          </div>
          {stocksLoading ? (
            <div className="page-loading"><RefreshCw size={20} className="spin"/><span>Loading stock data…</span></div>
          ) : (
            <div className="heatmap-grid">
              {stocks.map(s => {
                const pct = s.percent_change || 0;
                const colors = getHeatColor(pct);
                return (
                  <div
                    key={s.symbol}
                    className="heatmap-cell"
                    style={{ background: colors.bg, borderColor: colors.border, cursor: 'pointer' }}
                    onClick={() => handleStockClick(s.symbol)}
                  >
                    <span className="hc-symbol">{s.symbol}</span>
                    <span className="mono" style={{ fontSize:11, color:'var(--text-secondary)' }}>
                      ₹{s.price?.toLocaleString('en-IN', { maximumFractionDigits:1 })}
                    </span>
                    <span className={`hc-change ${pct >= 0 ? 'text-profit':'text-loss'}`}>
                      {pct >= 0 ? '+':''}{pct.toFixed(2)}%
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Table View */}
      {view === 'table' && (
        <div className="card history-table-card">
          <div style={{ padding:'16px 20px', borderBottom:'1px solid var(--border-color)', fontWeight:700, fontSize:14 }}>
            Nifty 50 — Live Quotes
          </div>
          {stocksLoading ? (
            <div className="table-loading">Loading…</div>
          ) : (
            <div className="table-wrapper">
              <table className="history-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Symbol</th>
                    <th>LTP</th>
                    <th>Change</th>
                    <th>% Change</th>
                    <th>Trend</th>
                  </tr>
                </thead>
                <tbody>
                  {stocks.sort((a,b)=>(b.percent_change||0)-(a.percent_change||0)).map((s,i) => {
                    const up = (s.percent_change||0) >= 0;
                    return (
                      <tr key={s.symbol} className="hist-row" style={{ cursor: 'pointer' }} onClick={() => handleStockClick(s.symbol)}>
                        <td style={{ color:'var(--text-muted)', fontWeight:700 }}>{i+1}</td>
                        <td className="fw-bold">{s.symbol}</td>
                        <td className="mono fw-bold">₹{s.price?.toLocaleString('en-IN', { minimumFractionDigits:2 })}</td>
                        <td className={`mono ${up?'text-profit':'text-loss'}`}>
                          {up?'+':''}{(s.change||0).toFixed(2)}
                        </td>
                        <td className={`mono fw-bold ${up?'text-profit':'text-loss'}`}>
                          {up?'+':''}{(s.percent_change||0).toFixed(2)}%
                        </td>
                        <td>
                          {up
                            ? <TrendingUp size={16} color="var(--green-profit)"/>
                            : <TrendingDown size={16} color="var(--red-loss)"/>
                          }
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Chart Modal Overlay */}
      {selectedStock && (
        <div className="modal-backdrop" style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(5, 5, 10, 0.85)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: 20,
        }}>
          <div className="card" style={{
            width: '100%',
            maxWidth: 800,
            background: 'rgba(10, 15, 30, 0.95)',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 4,
            boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}>
            <div style={{
              padding: '16px 20px',
              borderBottom: '1px solid rgba(255,255,255,0.05)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 12
            }}>
              <div>
                <h3 style={{ margin: 0, fontWeight: 700, fontSize: 18, color: 'var(--text-primary)' }}>
                  {selectedStock.replace('.NS', '')} Candlestick Chart
                </h3>
                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                  {timeframe === '5d' && '5-Minute Candles (Last 5 Days)'}
                  {timeframe === '1m' && '1-Hour Candles (Last 30 Days)'}
                  {timeframe === '1y' && 'Daily Candles (Last 1 Year)'}
                  {timeframe === '5y' && 'Daily Candles (Last 5 Years)'}
                </span>
              </div>
              
              <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                {/* Timeframe Selector Tabs */}
                <div style={{ display: 'flex', background: 'rgba(255,255,255,0.03)', borderRadius: 6, padding: 3, border: '1px solid rgba(255,255,255,0.05)' }}>
                  {['5d', '1m', '1y', '5y'].map((tf) => (
                    <button
                      key={tf}
                      onClick={() => handleTimeframeChange(tf)}
                      style={{
                        background: timeframe === tf ? 'var(--accent-cyan)' : 'transparent',
                        color: timeframe === tf ? '#000' : 'var(--text-secondary)',
                        border: 'none',
                        padding: '4px 10px',
                        borderRadius: 4,
                        fontSize: 11,
                        fontWeight: 700,
                        cursor: 'pointer',
                        transition: 'all 0.2s',
                        textTransform: 'uppercase'
                      }}
                    >
                      {tf === '5d' && '5D'}
                      {tf === '1m' && '1M'}
                      {tf === '1y' && '1Y'}
                      {tf === '5y' && '5Y'}
                    </button>
                  ))}
                </div>

                <button
                  onClick={() => setSelectedStock(null)}
                  style={{
                    background: 'rgba(255,255,255,0.05)',
                    border: 'none',
                    color: 'var(--text-muted)',
                    padding: '6px 12px',
                    borderRadius: 6,
                    cursor: 'pointer',
                    fontWeight: 600,
                    fontSize: 12,
                    transition: 'all 0.2s'
                  }}
                  onMouseEnter={(e) => { e.target.style.background = 'rgba(255,255,255,0.1)'; e.target.style.color = '#fff'; }}
                  onMouseLeave={(e) => { e.target.style.background = 'rgba(255,255,255,0.05)'; e.target.style.color = 'var(--text-muted)'; }}
                >
                  Close
                </button>
              </div>
            </div>
            
            <div style={{ padding: 20, flex: 1, minHeight: 350, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {chartLoading ? (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
                  <RefreshCw size={30} className="spin" style={{ color: 'var(--accent-cyan)' }} />
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Fetching live NSE chart data…</span>
                </div>
              ) : chartData.length > 0 ? (
                <CandlestickChart data={chartData} height={350} />
              ) : (
                <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No historical candles available for this symbol.</div>
              )}
            </div>

            <div style={{
              padding: '14px 20px',
              borderTop: '1px solid rgba(255,255,255,0.05)',
              background: 'rgba(255,255,255,0.01)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center'
            }}>
              <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                Click "Inspect Ticker" to run a full 5-agent AI evaluation on this stock.
              </span>
              <button
                onClick={() => {
                  const ticker = selectedStock.replace('.NS', '');
                  setSearchTicker(ticker);
                  setSelectedStock(null);
                  runAnalysis(ticker);
                }}
                className="btn-primary"
                style={{ padding: '6px 14px' }}
              >
                Inspect Ticker
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};


export default Market;
