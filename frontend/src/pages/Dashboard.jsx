import React, { useState, useEffect } from 'react';
import { 
    TrendingUp, 
    TrendingDown, 
    Activity, 
    DollarSign,
    ArrowUpRight,
    Search,
    Shield,
    Zap,
    Briefcase
} from 'lucide-react';
import { brokerAPI, marketAPI, performanceAPI } from '../services/api';

const StatCard = ({ title, value, subValue, icon, trend, color }) => (
    <div className="card stat-card" style={{ borderLeft: `4px solid ${color || 'var(--border-color)'}` }}>
        <div className="stat-header">
            <div className="stat-icon" style={{ background: `${color}15`, color: color }}>{icon}</div>
            <span className="stat-title">{title}</span>
        </div>
        <div className="stat-body">
            <h2 className="stat-value">{value}</h2>
            <div className={`stat-trend ${trend > 0 ? 'up' : 'down'}`}>
                {trend > 0 ? <ArrowUpRight size={14} /> : <TrendingDown size={14} />}
                <span>{subValue}</span>
            </div>
        </div>
    </div>
);

const Dashboard = () => {
    const [indices, setIndices] = useState([]);
    const [positions, setPositions] = useState([]);
    const [trades, setTrades] = useState([]);
    const [leaderboard, setLeaderboard] = useState([]);
    const [loading, setLoading] = useState(true);
    
    useEffect(() => {
        const fetchData = async () => {
            try {
                // Fetch each with its own error handling to prevent blocking
                const [idxRes, posRes, tradeRes, lbRes] = await Promise.allSettled([
                    marketAPI.getIndices(),
                    brokerAPI.getPositions(),
                    brokerAPI.getTrades(),
                    brokerAPI.getLeaderboard()
                ]);

                if (idxRes.status === 'fulfilled') setIndices(idxRes.value.data);
                if (posRes.status === 'fulfilled') setPositions(posRes.value.data);
                if (tradeRes.status === 'fulfilled') setTrades(tradeRes.value.data.slice(0, 6));
                if (lbRes.status === 'fulfilled') setLeaderboard(lbRes.value.data);
                
            } catch (err) {
                console.error("Critical dashboard fetch error", err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
        const interval = setInterval(fetchData, 10000);
        return () => clearInterval(interval);
    }, []);

    const totalEquity = leaderboard.reduce((acc, agent) => acc + agent.cash_balance, 0);
    const totalPnl = leaderboard.reduce((acc, agent) => acc + agent.total_pnl, 0);

    if (loading) return <div className="loading-screen">Booting Terminal...</div>;

    return (
        <div className="dashboard animate-fade-in">
            <header className="page-header">
                <div>
                    <h1>Terminal Alpha</h1>
                    <p className="subtitle">Live monitoring of NSE evaluation fleet</p>
                </div>
                <div className="header-actions">
                    <div className="search-bar">
                        <Search size={18} />
                        <input type="text" placeholder="Search portfolio..." />
                    </div>
                    <div className="market-badge">
                        <div className="pulse-dot green"></div>
                        NSE LIVE
                    </div>
                </div>
            </header>

            <div className="indices-grid">
                {indices.map(idx => (
                    <div key={idx.symbol} className="index-item animate-slide-up">
                        <span className="index-name">{idx.symbol}</span>
                        <span className="index-price">₹{idx.price.toLocaleString()}</span>
                        <span className={`index-change ${idx.percent_change >= 0 ? 'up' : 'down'}`}>
                            {idx.percent_change >= 0 ? '+' : ''}{idx.percent_change.toFixed(2)}%
                        </span>
                    </div>
                ))}
            </div>



            <div className="stats-grid">
                <StatCard 
                    title="Evaluation Equity" 
                    value={`₹${totalEquity.toLocaleString()}`} 
                    subValue="System Total" 
                    icon={<DollarSign size={20} />} 
                    trend={1}
                    color="#3b82f6"
                />
                <StatCard 
                    title="Active Positions" 
                    value={positions.length} 
                    subValue="Across Fleet" 
                    icon={<Briefcase size={20} />} 
                    trend={positions.length > 0 ? 1 : 0}
                    color="#a855f7"
                />
                <StatCard 
                    title="Net PnL" 
                    value={`₹${totalPnl.toLocaleString()}`} 
                    subValue={`${totalPnl >= 0 ? 'Profit' : 'Loss'} realized`} 
                    icon={<Activity size={20} />} 
                    trend={totalPnl >= 0 ? 1 : -1}
                    color={totalPnl >= 0 ? "var(--green-profit)" : "var(--red-loss)"}
                />
                <StatCard 
                    title="India VIX" 
                    value={indices.find(i => i.symbol === 'India VIX')?.price.toFixed(2) || "14.20"} 
                    subValue="Market Risk" 
                    icon={<Shield size={20} />} 
                    trend={-1}
                    color="#ef4444"
                />
            </div>

            <div className="main-grid">
                <section className="leaderboard-section card animate-slide-left">
                    <div className="section-header">
                        <h3 className="section-title"><Zap size={18} color="var(--accent-blue)" /> AI Agent Leaderboard</h3>
                        <span className="badge">LIVE STATS</span>
                    </div>
                    <div className="leaderboard-table">
                        <div className="table-header">
                            <span>Agent</span>
                            <span>Net PnL</span>
                            <span>Win Rate</span>
                            <span>Trades</span>
                            <span>Balance</span>
                        </div>
                        {leaderboard.map((agent, i) => (
                            <div key={agent.id} className="table-row hover-effect">
                                <span className="agent-name-cell">
                                    <div className="rank">{i + 1}</div>
                                    <div className="agent-avatar" style={{ background: agent.color }}>{agent.name[0]}</div>
                                    <div className="name-wrap">
                                        <div className="name">{agent.name}</div>
                                        <div className="sub">Active</div>
                                    </div>
                                </span>
                                <span className={`font-mono font-bold ${agent.total_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                                    {agent.total_pnl >= 0 ? '+' : ''}₹{agent.total_pnl.toLocaleString()}
                                </span>
                                <span className="font-mono">{agent.win_rate}</span>
                                <span className="font-mono">{agent.trades_count}</span>
                                <span className="font-mono">₹{agent.cash_balance.toLocaleString()}</span>
                            </div>
                        ))}
                    </div>
                </section>

                <div className="right-sidebar-grid">
                    <section className="recent-trades-section card animate-slide-right">
                        <h3 className="section-title">Terminal Activity</h3>
                        <div className="activity-list">
                            {trades.length > 0 ? trades.map(trade => (
                                <div key={trade.id} className="activity-item">
                                    <div className={`activity-indicator ${trade.pnl > 0 ? 'profit' : trade.pnl < 0 ? 'loss' : 'neutral'}`}></div>
                                    <div className="activity-info">
                                        <div className="top">
                                            <span className="symbol">{trade.symbol}</span>
                                            <span className={`pnl font-mono ${trade.pnl > 0 ? 'text-profit' : trade.pnl < 0 ? 'text-loss' : 'text-muted'}`}>
                                                {trade.pnl ? (trade.pnl > 0 ? '+' : '') + `₹${trade.pnl.toFixed(0)}` : 'OPEN'}
                                            </span>
                                        </div>
                                        <div className="bottom">
                                            <span>{trade.position_type} @ ₹{trade.entry_price}</span>
                                            <span className="time">{new Date(trade.entry_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                        </div>
                                    </div>
                                </div>
                            )) : (
                                <div className="empty-state">No recent activity</div>
                            )}
                        </div>
                    </section>

                    <section className="live-positions-summary card animate-slide-right delay-100">
                        <h3 className="section-title">Open Exposure</h3>
                        {positions.length > 0 ? (
                            <div className="mini-positions">
                                {positions.slice(0, 3).map(pos => (
                                    <div key={pos.id} className="mini-pos-item">
                                        <div className="left">
                                            <div className="sym">{pos.symbol}</div>
                                            <div className="type">{pos.position_type} x{pos.quantity}</div>
                                        </div>
                                        <div className={`right ${pos.unrealized_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                                            ₹{pos.unrealized_pnl.toFixed(2)}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="empty-state">No open exposure</div>
                        )}
                    </section>
                </div>
            </div>
        </div>
    );
};

export default Dashboard;
