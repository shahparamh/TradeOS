import React, { useState, useEffect } from 'react';
import { 
    Briefcase, TrendingUp, TrendingDown, Clock, Target, 
    ShieldAlert, XCircle, AlertTriangle, RefreshCw
} from 'lucide-react';
import { brokerAPI } from '../services/api';
import toast from 'react-hot-toast';

const PositionCard = ({ pos, onRefresh }) => {
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
                <div className="symbol-info">
                    <div className="agent-badge" style={{ background: agentColors[pos.agent_id] || 'var(--accent-blue)' }}>
                        {pos.agent_name || `Agent ${pos.agent_id}`}
                    </div>
                    <span className="symbol-name">{pos.symbol.replace('.NS', '')}</span>
                    <span className={`pos-type-badge ${pos.position_type.toLowerCase()}`}>{pos.position_type}</span>
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

    useEffect(() => {
        fetchPositions();
        const interval = setInterval(fetchPositions, 5000);
        return () => clearInterval(interval);
    }, []);

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
                        <PositionCard key={pos.id} pos={pos} onRefresh={fetchPositions} />
                    ))}
                </div>
            )}
        </div>
    );
};

export default Positions;
