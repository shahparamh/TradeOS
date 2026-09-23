import { useState, useEffect } from 'react';
import { X, RefreshCw } from 'lucide-react';
import { agentAPI } from '../services/api';
import { formatCurrency } from '../utils/currency';

const AgentDetailDrawer = ({ agentId, onClose }) => {
    const [agent, setAgent] = useState(null);
    const [trades, setTrades] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (!agentId) return;
        setLoading(true);
        Promise.all([agentAPI.getById(agentId), agentAPI.getAgentTrades(agentId)])
            .then(([agentRes, tradesRes]) => {
                setAgent(agentRes.data);
                setTrades(tradesRes.data.slice(0, 8));
            })
            .catch(() => {})
            .finally(() => setLoading(false));
    }, [agentId]);

    useEffect(() => {
        const handleEsc = (e) => { if (e.key === 'Escape') onClose(); };
        window.addEventListener('keydown', handleEsc);
        return () => window.removeEventListener('keydown', handleEsc);
    }, [onClose]);

    if (!agentId) return null;
    const stats = agent?.stats || {};
    const agentMarket = agent?.market || 'IN';
    const fmt = (amount, opts) => formatCurrency(amount, agentMarket, opts);

    return (
        <div className="drawer-overlay" onClick={onClose}>
            <div className="drawer-panel animate-slide-in" onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Agent detail">
                <div className="drawer-header">
                    <h3>{agent ? agent.name : 'Agent Detail'}</h3>
                    <button className="drawer-close" onClick={onClose} aria-label="Close drawer"><X size={16} /></button>
                </div>

                {loading ? (
                    <div className="panel-loading"><RefreshCw size={18} className="spin" /> Loading agent…</div>
                ) : !agent ? (
                    <div className="panel-empty">Could not load this agent.</div>
                ) : (
                    <div className="drawer-body">
                        <p className="drawer-subtitle mono">{agent.model_name} • {agent.provider}</p>

                        <div className="drawer-kpi-grid">
                            <div className="drawer-kpi">
                                <span className="kpi-label">Balance</span>
                                <span className="kpi-value mono">{fmt(agent.cash_balance)}</span>
                            </div>
                            <div className="drawer-kpi">
                                <span className="kpi-label">Net P&L</span>
                                <span className={`kpi-value mono ${agent.total_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                                    {agent.total_pnl >= 0 ? '+' : ''}{fmt(agent.total_pnl)}
                                </span>
                            </div>
                            <div className="drawer-kpi">
                                <span className="kpi-label">Win Rate</span>
                                <span className="kpi-value">{stats.closed_trades > 0 ? `${stats.win_rate}%` : '—'}</span>
                            </div>
                            <div className="drawer-kpi">
                                <span className="kpi-label">Open Positions</span>
                                <span className="kpi-value">{stats.open_positions ?? '—'}</span>
                            </div>
                        </div>

                        <h4 className="drawer-section-title">Recent Trades</h4>
                        {trades.length === 0 ? (
                            <div className="panel-empty">No trades recorded yet for this agent.</div>
                        ) : (
                            <div className="drawer-trade-list">
                                {trades.map(t => (
                                    <div className="drawer-trade-row" key={t.id}>
                                        <span className="mono fw-bold">{(t.symbol || '').replace('.NS', '')}</span>
                                        <span className="mono">{formatCurrency(t.entry_price, t.market || agentMarket)}</span>
                                        <span className={`mono ${t.pnl > 0 ? 'text-profit' : t.pnl < 0 ? 'text-loss' : 'text-muted'}`}>
                                            {t.pnl != null ? `${t.pnl > 0 ? '+' : ''}${formatCurrency(t.pnl, t.market || agentMarket)}` : 'OPEN'}
                                        </span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default AgentDetailDrawer;
