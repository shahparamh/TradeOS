import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Users, ArrowRight, RefreshCw } from 'lucide-react';
import { agentAPI } from '../services/api';
import { useMarket } from '../context/MarketContext';
import { formatCurrency } from '../utils/currency';

const AgentCard = ({ agent, rank }) => {
    const isProfit = agent.total_pnl >= 0;
    const agentMarket = agent.market || 'IN';
    const fmt = (amount, opts) => formatCurrency(amount, agentMarket, opts);
    const colorMap = {
        'gemini': 'var(--color-gemini)',
        'groq': 'var(--color-groq)',
        'chatgpt': 'var(--color-chatgpt)',
        'claude': 'var(--color-claude)',
        'grok': 'var(--color-grok)',
    };
    const colorKey = agent.name.toLowerCase().split('-')[0];
    const color = colorMap[colorKey] || 'var(--accent-blue)';

    return (
        <Link to={`/agent/${agent.id}`} className="agent-card card" style={{ textDecoration: 'none' }}>
            <div className="ac-rank">#{rank}</div>
            <div className="ac-header">
                <div className="ac-avatar" style={{ background: color }}>
                    {agent.name[0]}
                </div>
                <div className="ac-title">
                    <h3>{agent.name}</h3>
                    <p>{agent.model_name}</p>
                </div>
                <div className={`ac-status ${agent.is_active ? 'active' : 'inactive'}`}>
                    <span className="status-dot-sm"></span>
                    {agent.is_active ? 'Active' : 'Paused'}
                </div>
            </div>

            <div className="ac-stats">
                <div className="ac-stat">
                    <span className="as-label">Balance</span>
                    <span className="as-value mono">{fmt(agent.cash_balance, { maximumFractionDigits: 0, minimumFractionDigits: 0 })}</span>
                </div>
                <div className="ac-stat">
                    <span className="as-label">Net PnL</span>
                    <span className={`as-value mono ${isProfit ? 'text-profit' : 'text-loss'}`}>
                        {isProfit ? '+' : ''}{fmt(agent.total_pnl)}
                    </span>
                </div>
                <div className="ac-stat">
                    <span className="as-label">Win Rate</span>
                    <span className={`as-value ${agent.win_rate >= 50 ? 'text-profit' : 'text-loss'}`}>{agent.win_rate}%</span>
                </div>
                <div className="ac-stat">
                    <span className="as-label">Trades</span>
                    <span className="as-value">{agent.trades_count}</span>
                </div>
            </div>

            <div className="ac-pnl-bar">
                <div 
                    className={`ac-pnl-fill ${isProfit ? 'profit' : 'loss'}`}
                    style={{ width: `${Math.min(Math.abs(agent.total_pnl) / 1000 * 10, 100)}%` }}
                ></div>
            </div>

            <div className="ac-footer">
                <span className="provider-chip">{agent.provider}</span>
                <span className="view-link">View Detail <ArrowRight size={13} /></span>
            </div>
        </Link>
    );
};

const Agents = () => {
    const { market } = useMarket();
    const fmt = (amount, opts) => formatCurrency(amount, market, opts);
    const [agents, setAgents] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchAgents = () => {
        agentAPI.getAll()
            .then(res => { setAgents(res.data); setLoading(false); })
            .catch(() => setLoading(false));
    };

    useEffect(() => {
        fetchAgents();
        const interval = setInterval(fetchAgents, 15000);
        return () => clearInterval(interval);
    }, []);

    // Fleet agents aren't market-filtered server-side yet — filter client-side so an IN
    // agent's balance never gets summed/displayed next to a US agent's.
    const marketAgents = agents.filter(a => (a.market || 'IN') === market);
    const totalPnl = marketAgents.reduce((acc, a) => acc + a.total_pnl, 0);
    const totalTrades = marketAgents.reduce((acc, a) => acc + a.trades_count, 0);

    return (
        <div className="agents-page animate-fade-in">
            <header className="page-header">
                <div>
                    <h1>AI Trading Fleet</h1>
                    <p className="subtitle">Each agent operates with independent capital and risk parameters</p>
                </div>
                <div className="fleet-summary">
                    <div className="fs-item">
                        <span className="fs-label">Fleet PnL</span>
                        <span className={`fs-value ${totalPnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                            {totalPnl >= 0 ? '+' : ''}{fmt(totalPnl)}
                        </span>
                    </div>
                    <div className="fs-item">
                        <span className="fs-label">Total Trades</span>
                        <span className="fs-value">{totalTrades}</span>
                    </div>
                    <div className="fs-item">
                        <span className="fs-label">Active Agents</span>
                        <span className="fs-value text-profit">{marketAgents.filter(a => a.is_active).length}</span>
                    </div>
                </div>
            </header>

            {loading ? (
                <div className="page-loading">
                    <RefreshCw size={24} className="spin" />
                    <span>Loading agents...</span>
                </div>
            ) : marketAgents.length === 0 ? (
                <div className="empty-state-full card">
                    <Users size={56} color="var(--text-muted)" strokeWidth={1.5} />
                    <h2>No Agents Found</h2>
                    <p>Check that the backend is running and agents have been seeded.</p>
                </div>
            ) : (
                <div className="agents-grid">
                    {marketAgents.map((agent, i) => (
                        <AgentCard key={agent.id} agent={agent} rank={i + 1} />
                    ))}
                </div>
            )}
        </div>
    );
};

export default Agents;
