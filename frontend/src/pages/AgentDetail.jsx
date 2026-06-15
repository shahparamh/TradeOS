import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Shield, Zap, BarChart3, Clock } from 'lucide-react';
import { agentAPI } from '../services/api';

const AgentDetail = () => {
    const { agentId } = useParams();
    const [agent, setAgent] = useState(null);
    const [trades, setTrades] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [agentRes, tradesRes] = await Promise.all([
                    agentAPI.getById(agentId),
                    agentAPI.getAgentTrades(agentId),
                ]);
                setAgent(agentRes.data);
                setTrades(tradesRes.data);
            } catch (err) {
                console.error('Error loading agent', err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [agentId]);

    const handleToggleStatus = async () => {
        try {
            const res = await agentAPI.toggleStatus(agentId);
            if (res.data.status === 'success') {
                setAgent(prev => ({ ...prev, is_active: res.data.is_active }));
            }
        } catch (err) {
            console.error('Error toggling agent status', err);
        }
    };

    if (loading) return <div className="page-loading"><span>Loading agent profile...</span></div>;
    if (!agent) return <div className="page-loading"><span>Agent not found.</span></div>;

    const stats = agent.stats || {};
    const colorMap = {
        'gemini': 'var(--color-gemini)',
        'groq': 'var(--color-groq)',
        'chatgpt': 'var(--color-chatgpt)',
        'github': 'var(--color-github)',
    };
    const colorKey = agent.name.toLowerCase().split('-')[0];
    const agentColor = colorMap[colorKey] || 'var(--accent-blue)';

    const recentTrades = trades.slice(0, 10);

    return (
        <div className="agent-detail-page animate-fade-in">
            <div className="back-nav">
                <Link to="/agents" className="back-link">
                    <ArrowLeft size={16} /> Back to Fleet
                </Link>
            </div>

            <div className="agent-profile-header card">
                <div className="aph-left">
                    <div className="aph-avatar" style={{ background: agentColor }}>
                        {agent.name[0]}
                    </div>
                    <div className="aph-info">
                        <div className="aph-name-row">
                            <h1>{agent.name}</h1>
                            <span className={`status-chip ${agent.is_active ? 'active' : 'inactive'}`}>
                                {agent.is_active ? '● Active' : '● Paused'}
                            </span>
                            <button 
                                onClick={handleToggleStatus} 
                                className={`btn-toggle-status ${agent.is_active ? 'pause' : 'resume'}`}
                                style={{
                                    marginLeft: '12px',
                                    padding: '4px 10px',
                                    fontSize: '11px',
                                    fontWeight: '700',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    border: '1px solid',
                                    transition: 'all 0.2s',
                                    background: agent.is_active ? 'rgba(239, 68, 68, 0.08)' : 'rgba(16, 185, 129, 0.08)',
                                    color: agent.is_active ? '#ef4444' : '#10b981',
                                    borderColor: agent.is_active ? 'rgba(239, 68, 68, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                                }}
                            >
                                {agent.is_active ? 'Pause Agent' : 'Resume Agent'}
                            </button>
                        </div>
                        <p className="aph-model">{agent.model_name} • {agent.provider}</p>
                    </div>
                </div>
                <div className="aph-kpis">
                    <div className="kpi">
                        <span className="kpi-label">Balance</span>
                        <span className="kpi-value mono">₹{agent.cash_balance.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                    </div>
                    <div className="kpi">
                        <span className="kpi-label">Net PnL</span>
                        <span className={`kpi-value mono ${agent.total_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                            {agent.total_pnl >= 0 ? '+' : ''}₹{agent.total_pnl.toFixed(2)}
                        </span>
                    </div>
                    <div className="kpi">
                        <span className="kpi-label">Win Rate</span>
                        <span className={`kpi-value ${stats.win_rate >= 50 ? 'text-profit' : 'text-loss'}`}>
                            {stats.win_rate}%
                        </span>
                    </div>
                    <div className="kpi">
                        <span className="kpi-label">Total Trades</span>
                        <span className="kpi-value">{stats.total_trades}</span>
                    </div>
                </div>
            </div>

            <div className="ad-grid">
                <div className="ad-left">
                    <div className="card">
                        <h3 className="section-title"><BarChart3 size={16} /> Performance Stats</h3>
                        <div className="perf-grid">
                            <div className="perf-item">
                                <span className="pi-label">Closed Trades</span>
                                <span className="pi-value">{stats.closed_trades}</span>
                            </div>
                            <div className="perf-item">
                                <span className="pi-label">Open Positions</span>
                                <span className="pi-value text-profit">{stats.open_positions}</span>
                            </div>
                            <div className="perf-item">
                                <span className="pi-label">Today's Trades</span>
                                <span className="pi-value">{stats.today_trades}</span>
                            </div>
                            <div className="perf-item">
                                <span className="pi-label">Avg PnL / Trade</span>
                                <span className={`pi-value ${stats.avg_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                                    ₹{stats.avg_pnl?.toFixed(2) || '0.00'}
                                </span>
                            </div>
                            <div className="perf-item">
                                <span className="pi-label">Best Trade</span>
                                <span className="pi-value text-profit">+₹{stats.best_trade?.toFixed(2) || '0.00'}</span>
                            </div>
                            <div className="perf-item">
                                <span className="pi-label">Worst Trade</span>
                                <span className="pi-value text-loss">₹{stats.worst_trade?.toFixed(2) || '0.00'}</span>
                            </div>
                        </div>
                    </div>

                    <div className="card" style={{ marginTop: '24px' }}>
                        <h3 className="section-title"><Clock size={16} /> Recent Trades</h3>
                        {recentTrades.length === 0 ? (
                            <div className="table-empty">No trades yet.</div>
                        ) : (
                            <table className="mini-trade-table">
                                <thead>
                                    <tr>
                                        <th>Symbol</th>
                                        <th>Side</th>
                                        <th>Entry</th>
                                        <th>Exit</th>
                                        <th>PnL</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {recentTrades.map(t => (
                                        <tr key={t.id}>
                                            <td className="mono fw-bold">{t.symbol.replace('.NS', '')}</td>
                                            <td>
                                                <span className={`side-tag ${t.position_type?.toLowerCase()}`}>
                                                    {t.position_type}
                                                </span>
                                            </td>
                                            <td className="mono">₹{t.entry_price}</td>
                                            <td className="mono">{t.exit_price ? `₹${t.exit_price}` : '—'}</td>
                                            <td className={`mono fw-bold ${t.pnl > 0 ? 'text-profit' : t.pnl < 0 ? 'text-loss' : ''}`}>
                                                {t.pnl != null ? `${t.pnl > 0 ? '+' : ''}₹${t.pnl.toFixed(2)}` : 'OPEN'}
                                            </td>
                                            <td>
                                                <span className={`status-pill ${t.status?.toLowerCase().replace('_', '-')}`}>
                                                    {t.status}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </div>

                <div className="ad-right">
                    <div className="card">
                        <h3 className="section-title"><Shield size={16} /> Risk Status</h3>
                        <div className="risk-list">
                            <div className="risk-row">
                                <span>Circuit Breaker</span>
                                <span className="badge-pill safe">✓ SAFE</span>
                            </div>
                            <div className="risk-row">
                                <span>Open Positions</span>
                                <span>{stats.open_positions} / 5</span>
                            </div>
                            <div className="risk-row">
                                <span>Today's Trades</span>
                                <span>{stats.today_trades} / 3</span>
                            </div>
                            <div className="risk-row">
                                <span>Net PnL Today</span>
                                <span className={agent.total_pnl >= 0 ? 'text-profit' : 'text-loss'}>
                                    ₹{agent.total_pnl.toFixed(2)}
                                </span>
                            </div>
                        </div>
                    </div>

                    <div className="card" style={{ marginTop: '24px' }}>
                        <h3 className="section-title"><Zap size={16} /> Agent Profile</h3>
                        <div className="profile-list">
                            <div className="profile-row">
                                <span>Provider</span>
                                <span className="fw-bold">{agent.provider}</span>
                            </div>
                            <div className="profile-row">
                                <span>Model</span>
                                <span className="fw-bold mono">{agent.model_name}</span>
                            </div>
                            <div className="profile-row">
                                <span>Active Since</span>
                                <span>{agent.created_at ? new Date(agent.created_at).toLocaleDateString() : 'N/A'}</span>
                            </div>
                            <div className="profile-row">
                                <span>Wins / Losses</span>
                                <span>
                                    <span className="text-profit">{stats.total_wins}W</span>
                                    {' / '}
                                    <span className="text-loss">{stats.total_losses}L</span>
                                </span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default AgentDetail;
