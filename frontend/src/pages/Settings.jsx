import React, { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Key, Shield, Bell, Zap, Database, Save, CheckCircle, Newspaper } from 'lucide-react';
import toast from 'react-hot-toast';
import api, { settingsAPI } from '../services/api';

const ToggleSwitch = ({ value, onChange }) => (
    <div className={`toggle-switch ${value ? 'on' : ''}`} onClick={() => onChange(!value)}>
        <div className="toggle-knob"></div>
    </div>
);

const Settings = () => {
    const [config, setConfig] = useState({
        autoSquareOff: true,
        riskAlerts: true,
        emailNotif: false,
        voiceAlerts: false,
        geminiEnabled: true,
        groqEnabled: true,
        scanInterval: 5,
        maxPositions: 5,
        capitalPerTrade: 20,
    });

    const [rules, setRules] = useState({
        enable_loss_lockout: true,
        enable_short_selling: false,
        min_profit_threshold_pct: 0.015,
        enable_news_sentiment: true
    });
    
    const [loadingRules, setLoadingRules] = useState(true);

    useEffect(() => {
        const fetchRules = async () => {
            try {
                const response = await settingsAPI.getRules();
                const data = response.data;
                const loadedRules = {};
                Object.keys(data).forEach(key => {
                    loadedRules[key] = data[key].value;
                });
                setRules(loadedRules);
            } catch (error) {
                console.error("Failed to load rules", error);
                toast.error("Could not fetch live trading rules from database.");
            } finally {
                setLoadingRules(false);
            }
        };
        fetchRules();
    }, []);

    const handleSave = async () => {
        try {
            await settingsAPI.updateRules(rules);
            toast.success('Dynamic safety rules and configuration saved successfully!');
        } catch (error) {
            console.error("Failed to save rules", error);
            toast.error("Failed to save rules to database.");
        }
    };

    const setRule = (key, val) => setRules(prev => ({ ...prev, [key]: val }));
    const set = (key, val) => setConfig(prev => ({ ...prev, [key]: val }));

    return (
        <div className="settings-page animate-fade-in">
            <header className="page-header">
                <div>
                    <h1>System Settings</h1>
                    <p className="subtitle">Configure trading parameters, safety regulations, and AI behavior</p>
                </div>
                <button className="btn-primary" onClick={handleSave}>
                    <Save size={15} /> Save Rules & Config
                </button>
            </header>

            <div className="settings-grid">
                {/* Dynamic Trading Rules */}
                <div className="card settings-card">
                    <h3 className="section-title"><Shield size={16} /> Dynamic Safety Regulations</h3>
                    {loadingRules ? (
                        <div className="page-loading">
                            <span className="spin">⚡</span> Loading safety rules...
                        </div>
                    ) : (
                        <div className="settings-rows">
                            <div className="setting-row">
                                <div>
                                    <div className="sr-label">Single-Stock Loss Lockout</div>
                                    <div className="sr-desc">Prevent buying a stock for the day if a loss occurred on it today</div>
                                </div>
                                <ToggleSwitch value={rules.enable_loss_lockout} onChange={v => setRule('enable_loss_lockout', v)} />
                            </div>
                            <div className="setting-row">
                                <div>
                                    <div className="sr-label">Intraday Short-Selling</div>
                                    <div className="sr-desc">Permit agents to select SHORT sell positions during downtrends</div>
                                </div>
                                <ToggleSwitch value={rules.enable_short_selling} onChange={v => setRule('enable_short_selling', v)} />
                            </div>
                            <div className="setting-row">
                                <div>
                                    <div className="sr-label">Min Take-Profit Margin</div>
                                    <div className="sr-desc">Block orders where targets yield less than required margin</div>
                                </div>
                                <div className="number-input">
                                    <button onClick={() => setRule('min_profit_threshold_pct', Math.max(0.005, rules.min_profit_threshold_pct - 0.005))}>-</button>
                                    <span>{(rules.min_profit_threshold_pct * 100).toFixed(1)}%</span>
                                    <button onClick={() => setRule('min_profit_threshold_pct', Math.min(0.05, rules.min_profit_threshold_pct + 0.005))}>+</button>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* News Sentiment Regulation */}
                <div className="card settings-card">
                    <h3 className="section-title"><Newspaper size={16} /> Live News Regulations</h3>
                    <div className="settings-rows">
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">RSS News Stream Integration</div>
                                <div className="sr-desc">Pass live news sentiment into AI prompts to dynamically adapt strategies</div>
                            </div>
                            <ToggleSwitch value={rules.enable_news_sentiment} onChange={v => setRule('enable_news_sentiment', v)} />
                        </div>
                    </div>
                </div>

                {/* AI Agents settings */}
                <div className="card settings-card">
                    <h3 className="section-title"><Zap size={16} /> Multi-Agent AI Core</h3>
                    <div className="settings-rows">
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Auto Square-Off at 3:15 PM</div>
                                <div className="sr-desc">Forcibly liquidate open positions before close (9:15 - 3:15 IST)</div>
                            </div>
                            <ToggleSwitch value={config.autoSquareOff} onChange={v => set('autoSquareOff', v)} />
                        </div>
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Max Open Positions</div>
                                <div className="sr-desc">Simultaneous live open positions across all agents</div>
                            </div>
                            <div className="number-input">
                                <button onClick={() => set('maxPositions', Math.max(1, config.maxPositions - 1))}>-</button>
                                <span>{config.maxPositions}</span>
                                <button onClick={() => set('maxPositions', Math.min(20, config.maxPositions + 1))}>+</button>
                            </div>
                        </div>
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Capital Per Trade</div>
                                <div className="sr-desc">Max allocation % of simulated balance per trade</div>
                            </div>
                            <div className="number-input">
                                <button onClick={() => set('capitalPerTrade', Math.max(5, config.capitalPerTrade - 5))}>-</button>
                                <span>{config.capitalPerTrade}%</span>
                                <button onClick={() => set('capitalPerTrade', Math.min(50, config.capitalPerTrade + 5))}>+</button>
                            </div>
                        </div>
                    </div>
                </div>

                {/* System Info */}
                <div className="card settings-card">
                    <h3 className="section-title"><Database size={16} /> PostgreSQL Terminal Specs</h3>
                    <div className="settings-rows">
                        <div className="info-row">
                            <span>Database Connection</span>
                            <span className="text-profit">● Neon PostgreSQL Serverless (AWS)</span>
                        </div>
                        <div className="info-row">
                            <span>Session Guard</span>
                            <span className="badge-pill safe">JWT Authenticated</span>
                        </div>
                        <div className="info-row">
                            <span>Active Scheduler</span>
                            <span>Phase 7 Scheduler Loop</span>
                        </div>
                        <div className="info-row">
                            <span>Trading Environment</span>
                            <span className="badge-pill info">Paper Trading Simulation</span>
                        </div>
                    </div>
                </div>

                {/* System Automation (Scheduler Control) */}
                <div className="card settings-card">
                    <h3 className="section-title"><Database size={16} /> System Automation</h3>
                    <div className="settings-rows">
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Pre-Market Planner (9:00 AM IST)</div>
                                <div className="sr-desc">Trigger pre-market bias, boundaries, and trade rules setup</div>
                            </div>
                            <button className="btn-primary" onClick={async () => {
                                try {
                                    await api.post('/scheduler/pre-market');
                                    toast.success('Pre-market strategy session triggered in background');
                                } catch (e) { toast.error('Failed to trigger pre-market planner'); }
                            }} style={{ padding: '6px 12px', fontSize: '11px' }}>
                                Run Planner
                            </button>
                        </div>
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Trading Loop Cycle (9:15 AM - 3:15 PM IST)</div>
                                <div className="sr-desc">Trigger intraday agent scans and trade checks immediately</div>
                            </div>
                            <button className="btn-primary" onClick={async () => {
                                try {
                                    await api.post('/scheduler/trigger');
                                    toast.success('Main trading cycle triggered in background');
                                } catch (e) { toast.error('Failed to trigger cycle'); }
                            }} style={{ padding: '6px 12px', fontSize: '11px' }}>
                                Trigger Loop
                            </button>
                        </div>
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Position SL/TP Monitor</div>
                                <div className="sr-desc">Trigger manual stop-loss / take-profit tick update scans</div>
                            </div>
                            <button className="btn-primary" onClick={async () => {
                                try {
                                    await api.post('/scheduler/monitor');
                                    toast.success('Position check completed');
                                } catch (e) { toast.error('Failed to run monitor'); }
                            }} style={{ padding: '6px 12px', fontSize: '11px' }}>
                                Run Check
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Settings;
