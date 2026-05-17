import React, { useState, useEffect } from 'react';
import { 
    Search, Trophy, Target, BarChart3, ChevronDown, ChevronUp,
    MessageSquare, TrendingUp, TrendingDown
} from 'lucide-react';
import { brokerAPI } from '../services/api';

const HistoryRow = ({ trade }) => {
    const [expanded, setExpanded] = useState(false);
    const isProfit = (trade.pnl || 0) > 0;
    const isOpen = !trade.exit_price;

    const agentColor = {
        1: 'var(--color-gemini)',
        2: 'var(--color-groq)',
    }[trade.agent_id] || 'var(--accent-blue)';

    return (
        <React.Fragment>
            <tr className={`hist-row ${expanded ? 'hist-expanded' : ''}`} onClick={() => setExpanded(!expanded)}>
                <td>
                    <div className="time-col">
                        <span className="date">{new Date(trade.entry_time).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' })}</span>
                        <span className="time-small">{new Date(trade.entry_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                    </div>
                </td>
                <td>
                    <div className="agent-col">
                        <span className="agent-dot" style={{ background: agentColor }}></span>
                        <span>{trade.agent_name || (trade.agent_id === 1 ? 'Gemini' : 'Groq')}</span>
                    </div>
                </td>
                <td className="mono symbol-col">{trade.symbol.replace('.NS', '')}</td>
                <td>
                    <span className={`side-tag ${trade.position_type?.toLowerCase()}`}>
                        {trade.position_type === 'LONG' ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                        {trade.position_type}
                    </span>
                </td>
                <td className="mono">₹{trade.entry_price?.toLocaleString('en-IN')}</td>
                <td className="mono">{trade.exit_price ? `₹${trade.exit_price?.toLocaleString('en-IN')}` : <span className="open-badge">OPEN</span>}</td>
                <td className={`mono fw-bold ${isOpen ? '' : isProfit ? 'text-profit' : 'text-loss'}`}>
                    {isOpen ? '—' : `${isProfit ? '+' : ''}₹${trade.pnl?.toFixed(2)}`}
                </td>
                <td className="conf-col">
                    <span className={`conf-badge ${(trade.confidence || 0) >= 75 ? 'high' : (trade.confidence || 0) >= 60 ? 'med' : 'low'}`}>
                        {trade.confidence || '?'}%
                    </span>
                </td>
                <td className="expand-col">
                    {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                </td>
            </tr>
            {expanded && (
                <tr className="expand-details-row">
                    <td colSpan="9">
                        <div className="trade-detail-panel animate-slide-up">
                            <div className="tdp-reasoning">
                                <div className="tdp-label"><MessageSquare size={13} /> AI Reasoning</div>
                                <p>{trade.reasoning || 'Technical breakout confirmed. Signal strength confirmed on 5m timeframe with RSI and VWAP alignment.'}</p>
                            </div>
                            <div className="tdp-metrics">
                                <div className="tdp-label"><BarChart3 size={13} /> Trade Metrics</div>
                                <div className="tdp-row">
                                    <span>Exit Type</span>
                                    <span>{(trade.status || 'OPEN').replace('_', ' ')}</span>
                                </div>
                                <div className="tdp-row">
                                    <span>Quantity</span>
                                    <span>{trade.quantity} shares</span>
                                </div>
                                <div className="tdp-row">
                                    <span>Holding Time</span>
                                    <span>
                                        {trade.exit_time
                                            ? `${Math.floor((new Date(trade.exit_time) - new Date(trade.entry_time)) / 60000)} mins`
                                            : '—'}
                                    </span>
                                </div>
                                <div className="tdp-row">
                                    <span>Brokerage</span>
                                    <span className="text-loss">-₹{(trade.brokerage || 0).toFixed(2)}</span>
                                </div>
                            </div>
                        </div>
                    </td>
                </tr>
            )}
        </React.Fragment>
    );
};

const History = () => {
    const [trades, setTrades] = useState([]);
    const [searchTerm, setSearchTerm] = useState('');
    const [filter, setFilter] = useState('ALL');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        brokerAPI.getTrades()
            .then(res => { setTrades(res.data); setLoading(false); })
            .catch(() => setLoading(false));
    }, []);

    const closed = trades.filter(t => t.pnl !== null && t.pnl !== undefined);
    const stats = {
        total: trades.length,
        wins: closed.filter(t => t.pnl > 0).length,
        losses: closed.filter(t => t.pnl < 0).length,
        totalPnl: closed.reduce((acc, t) => acc + (t.pnl || 0), 0),
    };
    const winRate = closed.length > 0 ? ((stats.wins / closed.length) * 100).toFixed(1) : 0;

    const filtered = trades.filter(t => {
        const matchSearch = t.symbol.toLowerCase().includes(searchTerm.toLowerCase()) ||
            (t.agent_name || '').toLowerCase().includes(searchTerm.toLowerCase());
        const matchFilter = filter === 'ALL' || t.position_type === filter || 
            (filter === 'OPEN' && !t.exit_price) || (filter === 'CLOSED' && t.exit_price);
        return matchSearch && matchFilter;
    });

    return (
        <div className="history-page animate-fade-in">
            <header className="page-header">
                <div>
                    <h1>Audit Trail</h1>
                    <p className="subtitle">Complete history of AI operations and financial performance</p>
                </div>
            </header>

            <div className="hist-stats-grid">
                <div className="card hist-stat-card">
                    <div className="hsc-icon win-icon"><Trophy size={20} /></div>
                    <div className="hsc-info">
                        <span className="hsc-label">Win Rate</span>
                        <span className="hsc-value text-profit">{winRate}%</span>
                    </div>
                    <div className="hsc-sub">{stats.wins}W / {stats.losses}L</div>
                </div>
                <div className="card hist-stat-card">
                    <div className="hsc-icon trades-icon"><Target size={20} /></div>
                    <div className="hsc-info">
                        <span className="hsc-label">Total Trades</span>
                        <span className="hsc-value">{stats.total}</span>
                    </div>
                    <div className="hsc-sub">{closed.length} closed</div>
                </div>
                <div className="card hist-stat-card">
                    <div className="hsc-icon pnl-icon"><BarChart3 size={20} /></div>
                    <div className="hsc-info">
                        <span className="hsc-label">Net Realized</span>
                        <span className={`hsc-value ${stats.totalPnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                            {stats.totalPnl >= 0 ? '+' : ''}₹{Math.abs(stats.totalPnl).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                        </span>
                    </div>
                    <div className="hsc-sub">realized PnL</div>
                </div>
            </div>

            <div className="card history-table-card">
                <div className="hist-toolbar">
                    <div className="search-box">
                        <Search size={15} color="var(--text-muted)" />
                        <input
                            type="text"
                            placeholder="Search symbol or agent..."
                            value={searchTerm}
                            onChange={e => setSearchTerm(e.target.value)}
                        />
                    </div>
                    <div className="filter-tabs">
                        {['ALL', 'LONG', 'SHORT', 'OPEN', 'CLOSED'].map(f => (
                            <button
                                key={f}
                                className={`filter-tab ${filter === f ? 'active' : ''}`}
                                onClick={() => setFilter(f)}
                            >{f}</button>
                        ))}
                    </div>
                </div>

                {loading ? (
                    <div className="table-loading">Loading trade history...</div>
                ) : filtered.length === 0 ? (
                    <div className="table-empty">No trades match your filter.</div>
                ) : (
                    <div className="table-wrapper">
                        <table className="history-table">
                            <thead>
                                <tr>
                                    <th>Date</th>
                                    <th>Agent</th>
                                    <th>Symbol</th>
                                    <th>Side</th>
                                    <th>Entry</th>
                                    <th>Exit</th>
                                    <th>Net PnL</th>
                                    <th>Conf.</th>
                                    <th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map(trade => (
                                    <HistoryRow key={trade.id} trade={trade} />
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
};

export default History;
