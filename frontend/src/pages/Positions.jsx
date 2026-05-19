import React, { useState, useEffect } from 'react';
import { 
    Briefcase, TrendingUp, TrendingDown, Clock, Target, 
    ShieldAlert, XCircle, AlertTriangle, RefreshCw, BarChart2
} from 'lucide-react';
import api, { brokerAPI } from '../services/api';
import CandlestickChart from '../components/CandlestickChart';
import toast from 'react-hot-toast';

const PositionCard = ({ pos, onRefresh, onViewChart }) => {
    const pnl = pos.unrealized_pnl || 0;
    const isProfit = pnl >= 0;
    const invested = pos.entry_price * pos.quantity;
    const pnlPercent = invested > 0 ? ((pnl / invested) * 100).toFixed(2) : '0.00';
    const isNearSL = pos.stop_loss && Math.abs(pos.current_price - pos.stop_loss) / pos.current_price < 0.01;

    const handleClose = async () => {
        if (window.confirm(`Square off ${pos.symbol} at ₹${pos.current_price}?`)) {
            try {
                const res = await brokerAPI.closePosition(pos.id);
                toast.success(`✅ ${res.data.message}`);
                onRefresh();
            } catch (err) {
                toast.error(err.response?.data?.detail || 'Failed to close position');
            }
        }
    };

    const agentColors = {
        1: 'var(--color-gemini)',
        2: 'var(--color-groq)',
        3: 'var(--color-chatgpt)',
    };

    return (
        <div className={`card position-card ${isNearSL ? 'near-sl' : ''} ${pnl >= 0 ? 'card-profit' : 'card-loss'}`}>
            <div className="pos-header">
                <div className="symbol-info" style={{ cursor: 'pointer' }} onClick={() => onViewChart(pos)} title="View Live Chart">
                    <div className="agent-badge" style={{ background: agentColors[pos.agent_id] || 'var(--accent-blue)' }}>
                        {pos.agent_name || `Agent ${pos.agent_id}`}
                    </div>
                    <span className="symbol-name">{pos.symbol.replace('.NS', '')}</span>
                    <span className={`pos-type-badge ${pos.position_type.toLowerCase()}`}>{pos.position_type}</span>
                    <BarChart2 size={13} style={{ marginLeft: 6, color: 'var(--accent-cyan)' }} />
                </div>
                <button className="close-btn" onClick={handleClose} title="Manual Square Off">
                    <XCircle size={18} />
                    <span>Square Off</span>
                </button>
            </div>

            <div className="price-block">
                <div className="current-price">₹{pos.current_price.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</div>
                <div className={`pnl-badge ${isProfit ? 'profit' : 'loss'}`}>
                    {isProfit ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
                    <span>{isProfit ? '+' : ''}{pnlPercent}%</span>
                </div>
            </div>

            <div className={`unrealized-pnl mono ${isProfit ? 'text-profit' : 'text-loss'}`}>
                {isProfit ? '+' : ''}₹{Math.abs(pnl).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </div>

            <div className="pos-details-grid">
                <div className="detail-cell">
                    <span className="dc-label">Entry</span>
                    <span className="dc-value mono">₹{pos.entry_price}</span>
                </div>
                <div className="detail-cell">
                    <span className="dc-label">Qty</span>
                    <span className="dc-value">{pos.quantity}</span>
                </div>
                <div className="detail-cell">
                    <span className="dc-label">Type</span>
                    <span className="dc-value">{pos.trade_type || 'INTRADAY'}</span>
                </div>
            </div>

            <div className="risk-row">
                <div className="target-sl">
                    <Target size={13} color="var(--green-profit)" />
                    <span>TGT ₹{pos.target_price}</span>
                </div>
                <div className="target-sl">
                    <ShieldAlert size={13} color="var(--red-loss)" />
                    <span>SL ₹{pos.stop_loss}</span>
                </div>
            </div>

            <div className="pos-footer">
                <div className="time-row">
                    <Clock size={12} />
                    <span>{Math.floor((new Date() - new Date(pos.opened_at)) / 60000)} mins ago</span>
                </div>
                {isNearSL && (
                    <div className="sl-alert">
                        <AlertTriangle size={12} />
                        NEAR SL
                    </div>
                )}
            </div>
        </div>
    );
};

const Positions = () => {
    const [positions, setPositions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [lastUpdated, setLastUpdated] = useState(null);

    // Chart Modal States
    const [selectedStock, setSelectedStock] = useState(null);
    const [selectedPosition, setSelectedPosition] = useState(null);
    const [chartData, setChartData] = useState([]);
    const [chartLoading, setChartLoading] = useState(false);
    const [timeframe, setTimeframe] = useState('5d');
    const [liveTick, setLiveTick] = useState(null);

    const fetchPositions = async () => {
        try {
            const res = await brokerAPI.getPositions();
            setPositions(res.data);
            setLastUpdated(new Date());
        } catch (err) {
            console.error('Error fetching positions', err);
        } finally {
            setLoading(false);
        }
    };

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
            const formatted = res.data
                .filter(c => c && c.open !== null && c.high !== null && c.low !== null && c.close !== null)
                .map(c => {
                    const date = new Date(c.datetime);
                    const time = Math.floor(date.getTime() / 1000);
                    return {
                        time: time,
                        open: Number(c.open),
                        high: Number(c.high),
                        low: Number(c.low),
                        close: Number(c.close)
                    };
                })
                .filter(c => !isNaN(c.time) && !isNaN(c.open) && !isNaN(c.high) && !isNaN(c.low) && !isNaN(c.close))
                .filter((value, index, self) => self.findIndex(t => t.time === value.time) === index)
                .sort((a, b) => a.time - b.time);
            setChartData(formatted);
        } catch (err) {
            console.error("Failed to load chart data:", err);
        } finally {
            setChartLoading(false);
        }
    };

    const handleViewChart = (pos) => {
        setSelectedPosition(pos);
        setSelectedStock(pos.symbol);
        handleTimeframeChange('5d', pos.symbol);
    };

    useEffect(() => {
        fetchPositions();
        const interval = setInterval(fetchPositions, 10000); // Polling is now just a safety fallback, run it less often (10s)
        return () => clearInterval(interval);
    }, []);

    // Real-Time Live WebSocket Tick Connection
    useEffect(() => {
        const baseUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        
        let wsUrl;
        if (baseUrl.startsWith('http://') || baseUrl.startsWith('https://')) {
            const urlObj = new URL(baseUrl);
            wsUrl = `${wsProtocol}//${urlObj.host}/api/ws/market`;
        } else {
            wsUrl = `${wsProtocol}//${window.location.host}/api/ws/market`;
        }

        let socket;
        let reconnectTimeout;

        const connectWS = () => {
            console.log("[Positions WebSocket] Connecting to:", wsUrl);
            socket = new WebSocket(wsUrl);

            socket.onmessage = (event) => {
                try {
                    const message = JSON.parse(event.data);
                    if (message.type === 'MARKET_TICK') {
                        const tick = message.data; // e.g. { "symbol": "INFY.NS", "price": 1500, ... }
                        if (!tick || !tick.symbol) return;
                        
                        // 1. Instantly update current prices & PnL for active positions!
                        setPositions(prevPositions => prevPositions.map(pos => {
                            if (pos.symbol === tick.symbol) {
                                const priceVal = Number(tick.price);
                                const pnlVal = (pos.position_type === 'BUY') 
                                    ? (priceVal - pos.entry_price) * pos.quantity
                                    : (pos.entry_price - priceVal) * pos.quantity;
                                return {
                                    ...pos,
                                    current_price: priceVal,
                                    unrealized_pnl: pnlVal
                                };
                            }
                            return pos;
                        }));

                        // 2. If this tick is for the currently selected stock in the chart, update liveTick state!
                        if (selectedStock === tick.symbol) {
                            setLiveTick({
                                symbol: tick.symbol,
                                price: Number(tick.price),
                                change_pct: Number(tick.change_pct),
                                change: Number(tick.change),
                                volume: Number(tick.volume),
                                time: tick.time
                            });
                        }
                    }
                } catch (e) {
                    console.error("[Positions WebSocket] Failed to parse message:", e);
                }
            };

            socket.onclose = () => {
                console.log("[Positions WebSocket] Disconnected. Reconnecting in 3 seconds...");
                reconnectTimeout = setTimeout(connectWS, 3000);
            };

            socket.onerror = (err) => {
                console.error("[Positions WebSocket] Error:", err);
                socket.close();
            };
        };

        connectWS();

        return () => {
            if (socket) socket.close();
            if (reconnectTimeout) clearTimeout(reconnectTimeout);
        };
    }, [selectedStock]);

    const totalUnrealized = positions.reduce((acc, p) => acc + (p.unrealized_pnl || 0), 0);
    const profitCount = positions.filter(p => p.unrealized_pnl >= 0).length;
    const lossCount = positions.filter(p => p.unrealized_pnl < 0).length;

    if (loading) return (
        <div className="page-loading">
            <RefreshCw size={24} className="spin" />
            <span>Loading positions...</span>
        </div>
    );

    return (
        <div className="positions-page animate-fade-in">
            <header className="page-header">
                <div>
                    <h1>Live Positions</h1>
                    <p className="subtitle">Real-time fleet exposure & risk management</p>
                </div>
                <div className="pos-summary-bar">
                    <div className="summary-pill">
                        <span className="sp-label">Total Unrealized</span>
                        <span className={`sp-value mono ${totalUnrealized >= 0 ? 'text-profit' : 'text-loss'}`}>
                            {totalUnrealized >= 0 ? '+' : ''}₹{Math.abs(totalUnrealized).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </span>
                    </div>
                    <div className="summary-pill">
                        <span className="sp-label">Winning</span>
                        <span className="sp-value text-profit">{profitCount}</span>
                    </div>
                    <div className="summary-pill">
                        <span className="sp-label">Losing</span>
                        <span className="sp-value text-loss">{lossCount}</span>
                    </div>
                    <button className="refresh-btn" onClick={fetchPositions}>
                        <RefreshCw size={14} />
                        Refresh
                    </button>
                </div>
            </header>

            {positions.length === 0 ? (
                <div className="empty-state-full card animate-fade-in">
                    <Briefcase size={56} color="var(--text-muted)" strokeWidth={1.5} />
                    <h2>No Open Positions</h2>
                    <p>AI agents are scanning the market. Trades will appear here when executed.</p>
                    {lastUpdated && (
                        <span className="last-updated">
                            Last checked: {lastUpdated.toLocaleTimeString()}
                        </span>
                    )}
                </div>
            ) : (
                <div className="positions-grid">
                    {positions.map(pos => (
                        <PositionCard key={pos.id} pos={pos} onRefresh={fetchPositions} onViewChart={handleViewChart} />
                    ))}
                </div>
            )}

            {/* TradingView Candlestick Chart Modal Overlay */}
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
                        borderRadius: 12,
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
                                <h3 style={{ margin: 0, fontWeight: 700, fontSize: 18, color: '#fff' }}>
                                    {selectedStock.replace('.NS', '')} Chart
                                </h3>
                                <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
                                    {timeframe === '5d' && '5-Minute Candles (Last 5 Days)'}
                                    {timeframe === '1m' && '1-Hour Candles (Last 30 Days)'}
                                    {timeframe === '1y' && 'Daily Candles (Last 1 Year)'}
                                    {timeframe === '5y' && 'Daily Candles (Last 5 Years)'}
                                </span>
                            </div>
                            
                            <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
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
                                    onClick={() => {
                                        setSelectedStock(null);
                                        setSelectedPosition(null);
                                    }}
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
                                    <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Loading continuous chart data…</span>
                                </div>
                            ) : chartData.length > 0 ? (
                                <CandlestickChart 
                                    data={chartData} 
                                    liveTick={liveTick} 
                                    timeframe={timeframe}
                                    height={350} 
                                    entryPrice={selectedPosition?.entry_price}
                                    targetPrice={selectedPosition?.target_price}
                                    stopLoss={selectedPosition?.stop_loss}
                                />
                            ) : (
                                <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>No historical candles available for this symbol.</div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Positions;
