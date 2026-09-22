import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Skull, BarChart3, Clock, MessageSquare, ChevronDown, ChevronUp } from 'lucide-react';
import { arenaAPI } from '../services/api';

// Same per-provider identity color convention used on the Arena leaderboard and Fleet dashboard.
const PROVIDER_COLORS = {
    google: 'var(--color-gemini)',
    groq: 'var(--color-groq)',
    github: 'var(--color-github)',
    deepseek: 'var(--color-claude)',
    ollama: 'var(--color-chatgpt)',
};

const DebateStage = ({ label, children }) => {
    if (!children) return null;
    return (
        <div className="debate-stage">
            <span className="debate-stage-label">{label}</span>
            <div className="debate-stage-body">{children}</div>
        </div>
    );
};

const AnalystReport = ({ title, report }) => {
    if (!report) return null;
    return (
        <div className="analyst-report">
            <span className={`bias-tag bias-${(report.bias || 'neutral').toLowerCase()}`}>{title}: {report.bias || 'N/A'}</span>
            <p>{report.summary}</p>
        </div>
    );
};

const DebateTranscriptCard = ({ log }) => {
    const [open, setOpen] = useState(false);
    const reports = log.analyst_reports || {};
    const risk = Array.isArray(log.risk_team_debate) ? log.risk_team_debate : [];

    return (
        <div className="debate-log-card card">
            <button className="debate-log-header" onClick={() => setOpen(!open)}>
                <div>
                    <span className="mono fw-bold">{(log.symbol || '').replace('.NS', '')}</span>
                    <span className={`status-pill ${(log.final_action || '').toLowerCase()}`} style={{ marginLeft: 10 }}>
                        {log.final_action}
                    </span>
                </div>
                <div className="debate-log-header-right">
                    <span className="text-muted" style={{ fontSize: 11 }}>
                        {log.created_at ? new Date(log.created_at).toLocaleString() : ''}
                    </span>
                    {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>
            </button>

            {open && (
                <div className="debate-log-body">
                    <DebateStage label="1. Analyst Team">
                        <AnalystReport title="Technical" report={reports.technical} />
                        <AnalystReport title="Fundamentals" report={reports.fundamentals} />
                        <AnalystReport title="Sentiment" report={reports.sentiment} />
                    </DebateStage>

                    <DebateStage label="2. Researcher Debate">
                        {log.bull_argument?.argument && (
                            <p className="bull-argument">🐂 Bull: {log.bull_argument.argument}</p>
                        )}
                        {log.bear_argument?.argument && (
                            <p className="bear-argument">🐻 Bear: {log.bear_argument.argument}</p>
                        )}
                    </DebateStage>

                    <DebateStage label="3. Trader Proposal">
                        {log.trader_proposal && (
                            <p>
                                <span className={`side-tag ${(log.trader_proposal.decision || '').toLowerCase()}`}>{log.trader_proposal.decision}</span>
                                {' '}{log.trader_proposal.reasoning}
                            </p>
                        )}
                    </DebateStage>

                    {risk.length > 0 && (
                        <DebateStage label="4. Risk Team Review">
                            {risk.map((r, i) => (
                                <p key={i}><strong>{r.stance}:</strong> {r.recommendation} — {(r.concerns || []).join('; ')}</p>
                            ))}
                        </DebateStage>
                    )}

                    <DebateStage label="5. Portfolio Manager">
                        {log.portfolio_manager_decision && (
                            <p>
                                <span className={`side-tag ${(log.portfolio_manager_decision.decision || '').toLowerCase()}`}>{log.portfolio_manager_decision.decision}</span>
                                {' '}{log.portfolio_manager_decision.reasoning}
                            </p>
                        )}
                    </DebateStage>

                    <DebateStage label="6. Risk Engine Verdict">
                        {log.risk_engine_result && (
                            <p className={log.risk_engine_result.approved ? 'text-profit' : 'text-loss'}>
                                {log.risk_engine_result.approved
                                    ? `APPROVED — sized to ${log.risk_engine_result.quantity} shares`
                                    : `REJECTED — ${log.risk_engine_result.rejection_reason}`}
                            </p>
                        )}
                    </DebateStage>
                </div>
            )}
        </div>
    );
};

const ArenaAgentDetail = () => {
    const { agentId } = useParams();
    const [agent, setAgent] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        arenaAPI.getAgentDetail(agentId)
            .then(res => setAgent(res.data))
            .catch(err => console.error('Error loading arena agent', err))
            .finally(() => setLoading(false));
    }, [agentId]);

    if (loading) return <div className="page-loading"><span>Loading agent...</span></div>;
    if (!agent) return <div className="page-loading"><span>Agent not found.</span></div>;

    const stats = agent.stats || {};
    const isDead = agent.status === 'Dead';
    const avatarColor = isDead ? 'var(--text-muted)' : (PROVIDER_COLORS[agent.provider] || 'var(--accent-blue)');

    return (
        <div className="agent-detail-page animate-fade-in">
            <div className="back-nav">
                <Link to="/arena" className="back-link">
                    <ArrowLeft size={16} /> Back to Arena
                </Link>
            </div>

            <div className="agent-profile-header card">
                <div className="aph-left">
                    <div className="aph-avatar" style={{ background: avatarColor }}>
                        {isDead ? <Skull size={20} /> : agent.name[0]}
                    </div>
                    <div className="aph-info">
                        <div className="aph-name-row">
                            <h1>{agent.name}</h1>
                            <span className={`status-chip ${isDead ? 'inactive' : 'active'}`}>
                                {isDead ? `● Dead since ${new Date(agent.died_at).toLocaleDateString()}` : '● Alive'}
                            </span>
                        </div>
                        <p className="aph-model">{agent.model_name} • {agent.provider}</p>
                    </div>
                </div>
                <div className="aph-kpis">
                    <div className="kpi">
                        <span className="kpi-label">Equity</span>
                        <span className="kpi-value mono">₹{agent.equity.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                    </div>
                    <div className="kpi">
                        <span className="kpi-label">Return</span>
                        <span className={`kpi-value mono ${agent.return_pct >= 0 ? 'text-profit' : 'text-loss'}`}>
                            {agent.return_pct >= 0 ? '+' : ''}{agent.return_pct}%
                        </span>
                    </div>
                    <div className="kpi">
                        <span className="kpi-label">Win Rate</span>
                        <span className={`kpi-value ${stats.win_rate >= 50 ? 'text-profit' : 'text-loss'}`}>{stats.win_rate}%</span>
                    </div>
                    <div className="kpi">
                        <span className="kpi-label">Death Line</span>
                        <span className="kpi-value mono">₹{agent.death_threshold?.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                    </div>
                </div>
            </div>

            <div className="ad-grid">
                <div className="ad-left">
                    <div className="card">
                        <h3 className="section-title"><BarChart3 size={16} /> Performance Stats</h3>
                        <div className="perf-grid">
                            <div className="perf-item">
                                <span className="pi-label">Starting Capital</span>
                                <span className="pi-value mono">₹{agent.starting_capital?.toLocaleString('en-IN')}</span>
                            </div>
                            <div className="perf-item">
                                <span className="pi-label">Open Positions</span>
                                <span className="pi-value text-profit">{stats.open_positions}</span>
                            </div>
                            <div className="perf-item">
                                <span className="pi-label">Closed Trades</span>
                                <span className="pi-value">{stats.closed_trades}</span>
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
                        <h3 className="section-title"><Clock size={16} /> Trade History</h3>
                        {agent.trades.length === 0 ? (
                            <div className="table-empty">No trades yet.</div>
                        ) : (
                            <table className="mini-trade-table">
                                <thead>
                                    <tr><th>Symbol</th><th>Entry</th><th>Exit</th><th>PnL</th><th>Status</th></tr>
                                </thead>
                                <tbody>
                                    {agent.trades.slice(0, 15).map(t => (
                                        <tr key={t.id}>
                                            <td className="mono fw-bold">{(t.symbol || '').replace('.NS', '')}</td>
                                            <td className="mono">₹{t.entry_price}</td>
                                            <td className="mono">{t.exit_price ? `₹${t.exit_price}` : '—'}</td>
                                            <td className={`mono fw-bold ${t.pnl > 0 ? 'text-profit' : t.pnl < 0 ? 'text-loss' : ''}`}>
                                                {t.pnl != null ? `${t.pnl > 0 ? '+' : ''}₹${t.pnl.toFixed(2)}` : 'OPEN'}
                                            </td>
                                            <td><span className={`status-pill ${t.status?.toLowerCase().replace('_', '-')}`}>{t.status}</span></td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        )}
                    </div>
                </div>

                <div className="ad-right">
                    <div className="card">
                        <h3 className="section-title"><MessageSquare size={16} /> AI Reasoning — Debate Transcripts</h3>
                        <div className="debate-log-list">
                            {agent.debate_transcripts.length === 0 ? (
                                <div className="table-empty">No debate cycles logged yet.</div>
                            ) : (
                                agent.debate_transcripts.map(log => <DebateTranscriptCard key={log.id} log={log} />)
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ArenaAgentDetail;
