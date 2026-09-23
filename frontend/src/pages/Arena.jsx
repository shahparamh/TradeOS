import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Skull, ArrowRight, RefreshCw, Siren, PlayCircle, Zap, Plus, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { arenaAPI } from '../services/api';

const PROVIDER_OPTIONS = [
    { value: 'google', label: 'Google Gemini', defaultModel: 'gemini-3.1-flash-lite' },
    { value: 'groq', label: 'Groq', defaultModel: 'openai/gpt-oss-120b' },
    { value: 'github', label: 'GitHub Models', defaultModel: 'gpt-4o' },
    { value: 'deepseek', label: 'DeepSeek', defaultModel: 'deepseek-reasoning' },
    { value: 'ollama', label: 'Local Ollama', defaultModel: 'llama3.2' },
];

const CreateGameModal = ({ onClose, onCreated }) => {
    const [name, setName] = useState('');
    const [provider, setProvider] = useState(PROVIDER_OPTIONS[0].value);
    const [modelName, setModelName] = useState(PROVIDER_OPTIONS[0].defaultModel);
    const [startingCapital, setStartingCapital] = useState(2000);
    const [deathThreshold, setDeathThreshold] = useState('');
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState(null);

    const handleProviderChange = (value) => {
        setProvider(value);
        const opt = PROVIDER_OPTIONS.find(p => p.value === value);
        setModelName(opt ? opt.defaultModel : '');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!name.trim() || !modelName.trim()) {
            setError('Name and model are required.');
            return;
        }
        setSubmitting(true);
        setError(null);
        try {
            await arenaAPI.createAgent({
                name: name.trim(),
                provider,
                model_name: modelName.trim(),
                starting_capital: Number(startingCapital) || 2000,
                death_threshold: deathThreshold === '' ? null : Number(deathThreshold),
            });
            toast.success(`"${name.trim()}" entered the Survival Arena.`);
            onCreated();
            onClose();
        } catch (err) {
            const msg = err.response?.data?.detail || 'Failed to create survival agent.';
            setError(msg);
            toast.error(msg);
        } finally {
            setSubmitting(false);
        }
    };

    const inputStyle = {
        width: '100%',
        padding: '8px 10px',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--border-color)',
        background: 'var(--bg-primary)',
        color: 'var(--text-primary)',
        fontSize: 13,
        outline: 'none',
    };
    const labelStyle = { fontSize: 11, color: 'var(--text-muted)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.4, marginBottom: 6, display: 'block' };

    return (
        <div className="modal-backdrop" style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
            background: 'rgba(5, 5, 10, 0.85)', backdropFilter: 'blur(8px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            zIndex: 1000, padding: 20,
        }} onClick={onClose}>
            <form
                className="card"
                onClick={(e) => e.stopPropagation()}
                onSubmit={handleSubmit}
                style={{
                    width: '100%', maxWidth: 440,
                    background: 'rgba(10, 15, 30, 0.97)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    borderRadius: 4,
                    boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
                    overflow: 'hidden',
                }}
            >
                <div style={{ padding: '16px 20px', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ margin: 0, fontWeight: 700, fontSize: 16, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Skull size={16} /> New Survival Game
                    </h3>
                    <button type="button" onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4 }}>
                        <X size={18} />
                    </button>
                </div>

                <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                        Drop a new AI agent into the arena with its own paper balance. It trades autonomously until it doubles down or drops below its death line.
                    </p>

                    <div>
                        <label style={labelStyle}>Agent Name</label>
                        <input style={inputStyle} type="text" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. AgentZero-Beta" maxLength={40} required />
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                        <div>
                            <label style={labelStyle}>Provider</label>
                            <select style={inputStyle} value={provider} onChange={(e) => handleProviderChange(e.target.value)}>
                                {PROVIDER_OPTIONS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}
                            </select>
                        </div>
                        <div>
                            <label style={labelStyle}>Model</label>
                            <input style={inputStyle} type="text" value={modelName} onChange={(e) => setModelName(e.target.value)} required />
                        </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                        <div>
                            <label style={labelStyle}>Starting Capital (₹)</label>
                            <input style={inputStyle} type="number" min={100} step={100} value={startingCapital} onChange={(e) => setStartingCapital(e.target.value)} required />
                        </div>
                        <div>
                            <label style={labelStyle}>Death Line (₹, optional)</label>
                            <input style={inputStyle} type="number" min={0} step={50} value={deathThreshold} onChange={(e) => setDeathThreshold(e.target.value)} placeholder="10% of capital" />
                        </div>
                    </div>

                    {error && (
                        <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.25)', borderRadius: 4, padding: '10px 12px', color: 'var(--red-loss)', fontSize: 12 }}>
                            {error}
                        </div>
                    )}
                </div>

                <div style={{ padding: '14px 20px', borderTop: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                    <button type="button" onClick={onClose} className="refresh-btn" disabled={submitting}>Cancel</button>
                    <button type="submit" className="btn-primary" disabled={submitting}>
                        {submitting ? <RefreshCw size={14} className="spin" /> : <Plus size={14} />}
                        {submitting ? 'Creating...' : 'Start Game'}
                    </button>
                </div>
            </form>
        </div>
    );
};

// Distinct, consistent per-provider identity color — same convention used by the Fleet leaderboard —
// so competing Arena agents are visually distinguishable rather than uniformly blue.
const PROVIDER_COLORS = {
    google: 'var(--color-gemini)',
    groq: 'var(--color-groq)',
    github: 'var(--color-github)',
    deepseek: 'var(--color-claude)',
    ollama: 'var(--color-chatgpt)',
};

const AgentZeroCard = ({ agent, rank, onToggle, togglingId }) => {
    const isProfit = agent.return_pct >= 0;
    const isDead = agent.is_dead;
    const isPaused = agent.is_active === false;
    const isToggling = togglingId === agent.id;
    const avatarColor = isDead ? 'var(--text-muted)' : (PROVIDER_COLORS[agent.provider] || 'var(--accent-blue)');

    return (
        <Link to={`/arena/${agent.id}`} className={`agent-card card arena-card ${isDead ? 'dead' : ''} ${isPaused ? 'paused' : ''}`} style={{ textDecoration: 'none', position: 'relative' }}>
            <div className="ac-rank">#{rank}</div>
            <div className="ac-header">
                <div className="ac-avatar" style={{ background: avatarColor }}>
                    {isDead ? <Skull size={16} /> : agent.name[0]}
                </div>
                <div className="ac-title">
                    <h3>{agent.name}</h3>
                    <p>{agent.model_name}</p>
                </div>
                <div className={`ac-status ${isDead ? 'inactive' : 'active'}`}>
                    <span className="status-dot-sm"></span>
                    {isDead ? 'Dead' : isPaused ? 'Paused' : 'Alive'}
                </div>
            </div>

            <div className="ac-stats">
                <div className="ac-stat">
                    <span className="as-label">Equity</span>
                    <span className="as-value mono">₹{agent.equity.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                </div>
                <div className="ac-stat">
                    <span className="as-label">Return</span>
                    <span className={`as-value mono ${isProfit ? 'text-profit' : 'text-loss'}`}>
                        {isProfit ? '+' : ''}{agent.return_pct}%
                    </span>
                </div>
                <div className="ac-stat">
                    <span className="as-label">Survival</span>
                    <span className="as-value">{agent.survival_days ?? 0}d</span>
                </div>
                <div className="ac-stat">
                    <span className="as-label">Death Line</span>
                    <span className="as-value mono">₹{agent.death_threshold?.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                </div>
            </div>

            <div className="ac-footer" style={{ gap: 8 }}>
                <span className="provider-chip">{agent.provider}</span>
                <button
                    type="button"
                    onClick={(e) => { e.preventDefault(); e.stopPropagation(); onToggle(agent); }}
                    disabled={isDead || isToggling}
                    title={isPaused ? 'Resume this agent' : 'Deactivate this agent'}
                    style={{
                        display: 'flex', alignItems: 'center', gap: 4,
                        padding: '3px 8px', borderRadius: 6, fontSize: 10, fontWeight: 700,
                        border: '1px solid var(--border-color)',
                        background: isPaused ? 'rgba(56,217,150,0.12)' : 'rgba(255,102,115,0.1)',
                        color: isPaused ? 'var(--green-profit, #38D996)' : 'var(--red-loss, #FF6673)',
                        cursor: isDead ? 'not-allowed' : 'pointer',
                        opacity: isDead ? 0.4 : 1,
                        whiteSpace: 'nowrap',
                    }}
                >
                    {isToggling ? <RefreshCw size={11} className="spin" /> : (isPaused ? <PlayCircle size={11} /> : <Siren size={11} />)}
                    {isPaused ? 'Resume' : 'Deactivate'}
                </button>
                <span className="view-link">View Detail <ArrowRight size={13} /></span>
            </div>
        </Link>
    );
};

const Arena = () => {
    const [agents, setAgents] = useState([]);
    const [status, setStatus] = useState({ emergency_stop: false });
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [togglingId, setTogglingId] = useState(null);

    const fetchAll = () => {
        Promise.all([arenaAPI.getAgents(), arenaAPI.getStatus()])
            .then(([agentsRes, statusRes]) => {
                setAgents(agentsRes.data);
                setStatus(statusRes.data);
                setLoading(false);
            })
            .catch(() => setLoading(false));
    };

    useEffect(() => {
        fetchAll();
        const interval = setInterval(fetchAll, 15000);
        return () => clearInterval(interval);
    }, []);

    const handleToggleAgent = async (agent) => {
        setTogglingId(agent.id);
        try {
            await arenaAPI.toggleAgent(agent.id);
            toast.success(`${agent.name} ${agent.is_active === false ? 'resumed' : 'deactivated'}.`);
            fetchAll();
        } catch (err) {
            toast.error(err.response?.data?.detail || `Failed to update ${agent.name}.`);
        } finally {
            setTogglingId(null);
        }
    };

    const handleEmergencyToggle = async () => {
        setBusy(true);
        try {
            if (status.emergency_stop) {
                await arenaAPI.resume();
            } else {
                await arenaAPI.emergencyStop();
            }
            fetchAll();
        } catch (err) {
            console.error('Failed to toggle emergency stop', err);
        } finally {
            setBusy(false);
        }
    };

    const handleTriggerCycle = async () => {
        setBusy(true);
        try {
            await arenaAPI.triggerCycle();
        } catch (err) {
            console.error('Failed to trigger arena cycle', err);
        } finally {
            setBusy(false);
        }
    };

    const alive = agents.filter(a => !a.is_dead);
    const dead = agents.filter(a => a.is_dead);
    const totalCapital = agents.reduce((acc, a) => acc + (a.equity || 0), 0);
    const totalPnl = agents.reduce((acc, a) => acc + ((a.equity || 0) - (a.starting_capital || 0)), 0);

    return (
        <div className="agents-page arena-page animate-fade-in">
            <header className="page-header">
                <div>
                    <h1><Skull size={22} style={{ verticalAlign: 'text-bottom', marginRight: 8 }} />Survival Arena</h1>
                    <p className="subtitle">Give an AI a tiny paper balance. It either learns to survive the market — or dies.</p>
                </div>
                <div className="fleet-summary">
                    <div className="fs-item">
                        <span className="fs-label">Total Capital</span>
                        <span className="fs-value mono">₹{totalCapital.toLocaleString('en-IN', { maximumFractionDigits: 0 })}</span>
                    </div>
                    <div className="fs-item">
                        <span className="fs-label">Total P&L</span>
                        <span className={`fs-value ${totalPnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                            {totalPnl >= 0 ? '+' : ''}₹{totalPnl.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                        </span>
                    </div>
                    <div className="fs-item">
                        <span className="fs-label">Alive / Dead</span>
                        <span className="fs-value"><span className="text-profit">{alive.length}</span> / <span className="text-loss">{dead.length}</span></span>
                    </div>
                </div>
            </header>

            <div className="arena-controls card">
                <div className="arena-controls-left">
                    <span className={`badge ${status.emergency_stop ? 'badge-danger' : ''}`}>
                        {status.emergency_stop ? '⏸ EMERGENCY STOP ACTIVE' : '● Arena Live'}
                    </span>
                </div>
                <div className="arena-controls-right">
                    <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
                        <Plus size={14} /> New Game
                    </button>
                    <button className="refresh-btn" onClick={handleTriggerCycle} disabled={busy}>
                        <Zap size={14} /> Trigger Cycle
                    </button>
                    <button
                        className={`btn-primary ${status.emergency_stop ? 'btn-resume' : 'btn-emergency'}`}
                        onClick={handleEmergencyToggle}
                        disabled={busy}
                    >
                        {status.emergency_stop ? <PlayCircle size={16} /> : <Siren size={16} />}
                        {status.emergency_stop ? 'Resume Arena' : 'Emergency Stop'}
                    </button>
                </div>
            </div>

            {showCreateModal && (
                <CreateGameModal onClose={() => setShowCreateModal(false)} onCreated={fetchAll} />
            )}

            {loading ? (
                <div className="page-loading">
                    <RefreshCw size={24} className="spin" />
                    <span>Loading arena...</span>
                </div>
            ) : agents.length === 0 ? (
                <div className="empty-state-full card">
                    <Skull size={56} color="var(--text-muted)" strokeWidth={1.5} />
                    <h2>No Survival Agents Yet</h2>
                    <p>Check that the backend is running, or start a new game to drop an agent into the arena.</p>
                    <button className="btn-primary" style={{ marginTop: 12 }} onClick={() => setShowCreateModal(true)}>
                        <Plus size={14} /> New Game
                    </button>
                </div>
            ) : (
                <div className="agents-grid">
                    {agents.map((agent, i) => (
                        <AgentZeroCard key={agent.id} agent={agent} rank={i + 1} onToggle={handleToggleAgent} togglingId={togglingId} />
                    ))}
                </div>
            )}
        </div>
    );
};

export default Arena;
