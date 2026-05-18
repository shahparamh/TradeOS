import React, { useState, useEffect } from 'react';
import { Zap, Activity, Shield, TrendingUp } from 'lucide-react';
import { strategyAPI } from '../services/api';

const PreMarket = () => {
    const [strategies, setStrategies] = useState([]);
    const [loadingStrategy, setLoadingStrategy] = useState(true);
    const [expandedStrategyId, setExpandedStrategyId] = useState(null);

    const fetchStrategies = async () => {
        try {
            const res = await strategyAPI.getTodayPreMarket();
            setStrategies(res.data);
        } catch (err) {
            console.error("Failed to load pre-market strategy", err);
        } finally {
            setLoadingStrategy(false);
        }
    };

    const handleTriggerPreMarket = async () => {
        try {
            setLoadingStrategy(true);
            await strategyAPI.triggerPreMarket();
            // Wait 2.5 seconds for background execution and reload
            setTimeout(async () => {
                try {
                    const res = await strategyAPI.getTodayPreMarket();
                    setStrategies(res.data);
                } catch (e) {
                    console.error("Error refreshing pre-market strategy", e);
                } finally {
                    setLoadingStrategy(false);
                }
            }, 2500);
        } catch (err) {
            console.error("Failed to trigger pre-market planner", err);
            setLoadingStrategy(false);
        }
    };

    useEffect(() => {
        fetchStrategies();
        const interval = setInterval(fetchStrategies, 10000);
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="dashboard animate-fade-in">
            <header className="page-header" style={{ marginBottom: '24px' }}>
                <div>
                    <h1>AI Pre-Market Intel</h1>
                    <p className="subtitle">Daily stock selections, trading ranges, and logical reasoning calculated at 9:00 AM IST</p>
                </div>
                <div className="header-actions">
                    <button 
                        className="btn-primary trigger-pm-btn" 
                        onClick={handleTriggerPreMarket}
                        disabled={loadingStrategy}
                        style={{ 
                            padding: '10px 18px', 
                            fontSize: '13px', 
                            gap: '8px', 
                            background: 'rgba(99, 102, 241, 0.2)', 
                            border: '1px solid rgba(99, 102, 241, 0.4)', 
                            borderRadius: '8px', 
                            cursor: 'pointer', 
                            color: '#fff',
                            display: 'flex',
                            alignItems: 'center'
                        }}
                    >
                        ⚡ Run Planner Now
                    </button>
                </div>
            </header>

            {/* AI Pre-Market Strategy Panel */}
            <div className="card premarket-intel-card animate-fade-in" style={{ padding: '24px' }}>
                <div className="pm-card-header" style={{ marginBottom: '20px' }}>
                    <div className="pm-title-wrap">
                        <div className="pm-pulse-wrap">
                            <span className="pm-pulse"></span>
                            <h3 style={{ fontSize: '16px' }}>Active Daily Strategy Rules</h3>
                        </div>
                    </div>
                </div>

                {loadingStrategy ? (
                    <div className="pm-loading" style={{ padding: '60px 0' }}>
                        <div className="pulse-dot green" style={{ width: '14px', height: '14px', margin: '0 auto 15px auto' }}></div>
                        <span style={{ color: 'var(--text-secondary)' }}>Parsing daily macro signals and strategizing...</span>
                    </div>
                ) : strategies.length > 0 ? (
                    <div className="pm-strategies-list" style={{ gap: '14px' }}>
                        {strategies.map(s => {
                            const isExpanded = expandedStrategyId === s.id;
                            const biasClass = s.daily_bias === 'BULLISH' ? 'bias-bullish' : s.daily_bias === 'BEARISH' ? 'bias-bearish' : 'bias-neutral';
                            return (
                                <div key={s.id} className="pm-strategy-item">
                                    <div className="pm-item-summary" style={{ padding: '16px 20px' }} onClick={() => setExpandedStrategyId(isExpanded ? null : s.id)}>
                                        <div className="pm-item-left">
                                            <span className="pm-agent-badge" style={{ fontSize: '11px' }}>{s.agent_name}</span>
                                            <span className="pm-symbol" style={{ fontSize: '14px' }}>{s.symbol}</span>
                                            <span className={`badge ${biasClass}`} style={{ fontSize: '10px', padding: '3px 8px', borderRadius: '5px' }}>{s.daily_bias}</span>
                                        </div>
                                        <div className="pm-item-right">
                                            <div className="pm-boundaries" style={{ gap: '20px', fontSize: '13px' }}>
                                                <span>Range: <strong className="font-mono" style={{ color: 'var(--text-primary)' }}>₹{s.entry_lower_limit} - ₹{s.entry_upper_limit}</strong></span>
                                                <span>Target: <strong className="font-mono text-profit">₹{s.target_price}</strong></span>
                                                <span>SL: <strong className="font-mono text-loss">₹{s.stop_loss}</strong></span>
                                            </div>
                                            <span className="pm-toggle-icon">
                                                {isExpanded ? '▲' : '▼'}
                                            </span>
                                        </div>
                                    </div>
                                    {isExpanded && (
                                        <div className="pm-item-details animate-slide-down" style={{ padding: '18px 20px', background: 'rgba(15, 23, 42, 0.4)' }}>
                                            <h4 style={{ color: '#a855f7', marginBottom: '10px' }}>AI Execution Logic:</h4>
                                            <p className="pm-reasoning" style={{ fontSize: '13px', lineHeight: '1.7' }}>{s.reasoning}</p>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                ) : (
                    <div className="pm-empty-state" style={{ padding: '80px 0' }}>
                        <span style={{ fontSize: '15px' }}>🕒 Pre-Market Strategy session has not run today yet. Current bias is set to <strong>NEUTRAL</strong>.</span>
                        <p style={{ marginTop: '8px' }}>You can run it manually using the top action button, or wait for the TradeOS Scheduler to automatically trigger it at 9:00 AM IST.</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default PreMarket;
