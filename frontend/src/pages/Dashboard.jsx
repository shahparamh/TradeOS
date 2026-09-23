import React, { useState, useEffect, useCallback } from 'react';
import {
    TrendingUp,
    Activity,
    DollarSign,
    Briefcase,
    Users,
    Grid3x3,
} from 'lucide-react';
import { brokerAPI, marketAPI } from '../services/api';
import Watchlist from '../components/Watchlist';
import ChartPanel from '../components/ChartPanel';
import AgentDetailDrawer from '../components/AgentDetailDrawer';
import { NIFTY50_SYMBOLS, US_SYMBOLS } from '../utils/symbols';
import { useMarket } from '../context/MarketContext';
import { formatCurrency } from '../utils/currency';

const MetricCard = ({ label, value, detail, detailPositive, icon }) => (
    <div className="card metric-card">
        <div className="metric-card-top">
            <span className="metric-label">{label}</span>
            <span className="metric-icon">{icon}</span>
        </div>
        <div className="metric-value mono">{value}</div>
        {detail && (
            <div className={`metric-detail ${detailPositive === true ? 'text-profit' : detailPositive === false ? 'text-loss' : ''}`}>
                {detail}
            </div>
        )}
    </div>
);

const IN_HEATMAP_SYMBOLS = NIFTY50_SYMBOLS.slice(0, 12).map(s => `${s}.NS`);
const US_HEATMAP_SYMBOLS = US_SYMBOLS.slice(0, 12);

const getHeatColor = (pct) => {
    if (pct == null) return { bg: 'var(--bg-tertiary)', border: 'var(--border-color)' };
    if (pct > 2) return { bg: 'rgba(49,211,148,0.45)', border: 'rgba(49,211,148,0.5)' };
    if (pct > 0.5) return { bg: 'rgba(49,211,148,0.25)', border: 'rgba(49,211,148,0.3)' };
    if (pct > 0) return { bg: 'rgba(49,211,148,0.1)', border: 'rgba(49,211,148,0.15)' };
    if (pct > -0.5) return { bg: 'rgba(241,107,124,0.1)', border: 'rgba(241,107,124,0.15)' };
    if (pct > -2) return { bg: 'rgba(241,107,124,0.25)', border: 'rgba(241,107,124,0.3)' };
    return { bg: 'rgba(241,107,124,0.45)', border: 'rgba(241,107,124,0.5)' };
};

const Dashboard = () => {
    const { market } = useMarket();
    const fmt = (amount, opts) => formatCurrency(amount, market, opts);
    const [positions, setPositions] = useState([]);
    const [trades, setTrades] = useState([]);
    const [leaderboard, setLeaderboard] = useState([]);
    const [heatmapQuotes, setHeatmapQuotes] = useState({});
    const [loading, setLoading] = useState(true);
    const heatmapSymbols = market === 'US' ? US_HEATMAP_SYMBOLS : IN_HEATMAP_SYMBOLS;
    const defaultSymbol = market === 'US' ? 'AAPL' : 'RELIANCE.NS';
    const [selectedSymbol, setSelectedSymbol] = useState(defaultSymbol);
    const [selectedQuote, setSelectedQuote] = useState(null);
    const [drawerAgentId, setDrawerAgentId] = useState(null);

    // Reset the selected chart instrument to this market's default watchlist symbol when
    // switching markets — otherwise a US switch would keep charting a stale NSE symbol.
    useEffect(() => {
        setSelectedSymbol(defaultSymbol);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [market]);

    const fetchData = useCallback(async () => {
        try {
            const [posRes, tradeRes, lbRes, heatRes] = await Promise.allSettled([
                brokerAPI.getPositions(),
                brokerAPI.getTrades(),
                brokerAPI.getLeaderboard(),
                marketAPI.getPrices(heatmapSymbols),
            ]);

            if (posRes.status === 'fulfilled') setPositions(posRes.value.data);
            if (tradeRes.status === 'fulfilled') setTrades(tradeRes.value.data.slice(0, 8));
            if (lbRes.status === 'fulfilled') setLeaderboard(lbRes.value.data);
            if (heatRes.status === 'fulfilled') setHeatmapQuotes(heatRes.value.data);
        } catch (err) {
            console.error("Dashboard fetch error", err);
        } finally {
            setLoading(false);
        }
    }, [heatmapSymbols]);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 15000);
        return () => clearInterval(interval);
    }, [fetchData]);

    // Keep the chart panel's header quote in sync with whichever instrument is selected.
    useEffect(() => {
        let cancelled = false;
        marketAPI.getPrice(selectedSymbol).then(res => {
            if (!cancelled) setSelectedQuote(res.data);
        }).catch(() => {});
        return () => { cancelled = true; };
    }, [selectedSymbol]);

    const totalEquity = leaderboard.reduce((acc, agent) => acc + agent.cash_balance, 0);
    const totalPnl = leaderboard.reduce((acc, agent) => acc + agent.total_pnl, 0);
    const activeAgents = leaderboard.filter(a => a.is_active).length;

    if (loading) return <div className="loading-screen">Booting Terminal...</div>;

    return (
        <div className="dashboard animate-fade-in">
            <header className="page-header">
                <div>
                    <h1>Terminal Alpha</h1>
                    <p className="subtitle">Live monitoring of {market === 'US' ? 'US' : 'NSE'} evaluation fleet</p>
                </div>
                <div className="header-actions">
                    <div className="market-badge">
                        <div className="pulse-dot green"></div>
                        {market === 'US' ? 'US' : 'NSE'} LIVE
                    </div>
                </div>
            </header>

            {/* Row 1 — compact metric summaries */}
            <div className="metrics-row">
                <MetricCard
                    label="Total Equity"
                    value={fmt(totalEquity)}
                    detail="System total across fleet"
                    icon={<DollarSign size={15} />}
                />
                <MetricCard
                    label="Net P&L"
                    value={`${totalPnl >= 0 ? '+' : ''}${fmt(totalPnl)}`}
                    detail={totalPnl >= 0 ? 'Profit realized' : 'Loss realized'}
                    detailPositive={totalPnl >= 0}
                    icon={<Activity size={15} />}
                />
                <MetricCard
                    label="Open Positions"
                    value={positions.length}
                    detail="Across fleet"
                    icon={<Briefcase size={15} />}
                />
                <MetricCard
                    label="Active Agents"
                    value={`${activeAgents} / ${leaderboard.length}`}
                    detail="Evaluating live market"
                    icon={<Users size={15} />}
                />
            </div>

            {/* Row 2 — watchlist / chart / agent rankings */}
            <div className="workspace-row">
                <Watchlist selectedSymbol={selectedSymbol} onSelect={setSelectedSymbol} />
                <ChartPanel symbol={selectedSymbol} quote={selectedQuote} />

                <div className="card rankings-panel">
                    <div className="panel-title-bar">
                        <h3 className="panel-title"><TrendingUp size={14} /> AI Agent Rankings</h3>
                        <span className="badge">LIVE</span>
                    </div>
                    {leaderboard.length === 0 ? (
                        <div className="panel-empty">No agents configured.</div>
                    ) : (
                        <div className="rankings-rows">
                            {[...leaderboard].sort((a, b) => b.total_pnl - a.total_pnl).map((agent, i) => (
                                <button
                                    key={agent.id}
                                    className="ranking-row"
                                    onClick={() => setDrawerAgentId(agent.id)}
                                >
                                    <span className="rank-num">{i + 1}</span>
                                    <span className="rank-avatar" style={{ background: agent.color }}>{agent.name[0]}</span>
                                    <span className="rank-name">{agent.name}</span>
                                    <span className={`rank-pnl mono ${agent.total_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                                        {agent.total_pnl >= 0 ? '+' : ''}{fmt(agent.total_pnl, { maximumFractionDigits: 0, minimumFractionDigits: 0 })}
                                    </span>
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            {/* Row 3 — positions / heatmap / activity */}
            <div className="support-row">
                <div className="card support-panel positions-support">
                    <div className="panel-title-bar">
                        <h3 className="panel-title"><Briefcase size={14} /> Live Positions</h3>
                        <a href="/positions" className="panel-action">View All</a>
                    </div>
                    {positions.length === 0 ? (
                        <div className="panel-empty">No open positions. Agents are scanning the market.</div>
                    ) : (
                        <table className="support-table">
                            <thead>
                                <tr><th>Symbol</th><th>Agent</th><th>Qty</th><th className="num">LTP</th><th className="num">P&L</th></tr>
                            </thead>
                            <tbody>
                                {positions.slice(0, 6).map(p => (
                                    <tr key={p.id}>
                                        <td className="mono fw-bold">{(p.symbol || '').replace('.NS', '')}</td>
                                        <td>{p.agent_name || '—'}</td>
                                        <td className="mono">{p.quantity}</td>
                                        <td className="mono num">{p.current_price != null ? fmt(p.current_price) : '—'}</td>
                                        <td className={`mono num ${p.unrealized_pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                                            {p.unrealized_pnl >= 0 ? '+' : ''}{fmt(p.unrealized_pnl)}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>

                <div className="card support-panel heatmap-support">
                    <div className="panel-title-bar">
                        <h3 className="panel-title"><Grid3x3 size={14} /> Market Heatmap</h3>
                        <a href="/market" className="panel-action">Expand</a>
                    </div>
                    <div className="mini-heatmap-grid">
                        {heatmapSymbols.map(sym => {
                            const q = heatmapQuotes[sym];
                            const pct = q?.percent_change ?? null;
                            const colors = getHeatColor(pct);
                            return (
                                <div key={sym} className="mini-heatmap-tile" style={{ background: colors.bg, borderColor: colors.border }} title={q ? `${fmt(q.price)}${pct != null ? ` (${pct.toFixed(2)}%)` : ''}` : 'No data'}>
                                    <span className="mht-symbol mono">{sym.replace('.NS', '')}</span>
                                    <span className="mht-pct mono">{pct == null ? '—' : `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`}</span>
                                </div>
                            );
                        })}
                    </div>
                    <div className="heatmap-legend">
                        <span className="legend-swatch" style={{ background: 'rgba(241,107,124,0.45)' }}></span> Down
                        <span className="legend-swatch" style={{ background: 'var(--bg-tertiary)' }}></span> Flat
                        <span className="legend-swatch" style={{ background: 'rgba(49,211,148,0.45)' }}></span> Up
                    </div>
                </div>

                <div className="card support-panel activity-support">
                    <div className="panel-title-bar">
                        <h3 className="panel-title"><Activity size={14} /> Agent Activity</h3>
                    </div>
                    {trades.length === 0 ? (
                        <div className="panel-empty">No recorded agent activity yet.</div>
                    ) : (
                        <div className="activity-rows">
                            {trades.map(trade => (
                                <div key={trade.id} className="activity-row">
                                    <span className={`activity-dot ${trade.pnl > 0 ? 'profit' : trade.pnl < 0 ? 'loss' : 'neutral'}`}></span>
                                    <div className="activity-text">
                                        <span className="activity-primary">{trade.symbol?.replace('.NS', '')} · {trade.position_type} @ {fmt(trade.entry_price)}</span>
                                        <span className="activity-secondary">
                                            {trade.pnl != null ? `${trade.pnl > 0 ? '+' : ''}${fmt(trade.pnl, { maximumFractionDigits: 0, minimumFractionDigits: 0 })}` : 'Position open'}
                                            {' · '}
                                            {new Date(trade.entry_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>

            <AgentDetailDrawer agentId={drawerAgentId} onClose={() => setDrawerAgentId(null)} />
        </div>
    );
};

export default Dashboard;
