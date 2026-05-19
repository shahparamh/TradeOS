import React, { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Key, Shield, Bell, Zap, Database, Save, CheckCircle, Newspaper, Trash2, RefreshCw } from 'lucide-react';
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
        enable_loss_lockout: false,
        enable_short_selling: true,
        min_profit_threshold_pct: 0.005,
        enable_news_sentiment: true,
        max_open_positions: 40,
        max_capital_per_trade_pct: 0.50,
        max_intraday_trades: 70,
        daily_drawdown_limit: -0.05,
        min_confidence: 45,
        max_stop_loss_distance: 0.07,
        min_risk_reward_ratio: 1.0,
        max_consecutive_losses: 5,
        max_trades_per_stock_daily: 5,
        entry_start_hour: 9.25,
        entry_end_hour: 15.0,
        enable_fno_trading: true,
        starting_capital_per_agent: 5000000.0
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
                            <div className="setting-row">
                                <div>
                                    <div className="sr-label">Max Open Positions</div>
                                    <div className="sr-desc">Maximum simultaneous open positions per agent</div>
                                </div>
                                <div className="number-input">
                                    <button onClick={() => setRule('max_open_positions', Math.max(1, (rules.max_open_positions || 0) - 1))}>-</button>
                                    <span>{rules.max_open_positions || 0}</span>
                                    <button onClick={() => setRule('max_open_positions', Math.min(100, (rules.max_open_positions || 0) + 1))}>+</button>
                                </div>
                            </div>
                            <div className="setting-row">
                                <div>
                                    <div className="sr-label">Capital Per Trade Allocation</div>
                                    <div className="sr-desc">Maximum cash allocation per trade as percentage of balance</div>
                                </div>
                                <div className="number-input">
                                    <button onClick={() => setRule('max_capital_per_trade_pct', Math.max(0.05, (rules.max_capital_per_trade_pct || 0) - 0.05))}>-</button>
                                    <span>{((rules.max_capital_per_trade_pct || 0) * 100).toFixed(0)}%</span>
                                    <button onClick={() => setRule('max_capital_per_trade_pct', Math.min(1.00, (rules.max_capital_per_trade_pct || 0) + 0.05))}>+</button>
                                </div>
                            </div>
                            <div className="setting-row">
                                <div>
                                    <div className="sr-label">Max Daily Intraday Trades</div>
                                    <div className="sr-desc">Maximum intraday trades allowed per agent per day</div>
                                </div>
                                <div className="number-input">
                                    <button onClick={() => setRule('max_intraday_trades', Math.max(1, (rules.max_intraday_trades || 0) - 5))}>-</button>
                                    <span>{rules.max_intraday_trades || 0}</span>
                                    <button onClick={() => setRule('max_intraday_trades', Math.min(200, (rules.max_intraday_trades || 0) + 5))}>+</button>
                                </div>
                            </div>
                            <div className="setting-row">
                                <div>
                                    <div className="sr-label">Daily Drawdown Limit</div>
                                    <div className="sr-desc">Stop trading if daily losses exceed this % of capital</div>
                                </div>
                                <div className="number-input">
                                    <button onClick={() => setRule('daily_drawdown_limit', Math.max(-0.20, (rules.daily_drawdown_limit || 0) - 0.01))}>-</button>
                                    <span>{((rules.daily_drawdown_limit || 0) * 100).toFixed(0)}%</span>
                                    <button onClick={() => setRule('daily_drawdown_limit', Math.min(-0.01, (rules.daily_drawdown_limit || 0) + 0.01))}>+</button>
                                </div>
                            </div>
                            <div className="setting-row">
                                <div>
                                    <div className="sr-label">Min Confidence Floor</div>
                                    <div className="sr-desc">Minimum AI confidence score (0-100) required to enter trades</div>
                                </div>
                                <div className="number-input">
                                    <button onClick={() => setRule('min_confidence', Math.max(20, (rules.min_confidence || 0) - 5))}>-</button>
                                    <span>{rules.min_confidence || 0}%</span>
                                    <button onClick={() => setRule('min_confidence', Math.min(95, (rules.min_confidence || 0) + 5))}>+</button>
                                </div>
                            </div>
                            <div className="setting-row">
                                <div>
                                    <div className="sr-label">Max Stop Loss Distance</div>
                                    <div className="sr-desc">Maximum distance allowed from entry price for stop loss</div>
                                </div>
                                <div className="number-input">
                                    <button onClick={() => setRule('max_stop_loss_distance', Math.max(0.01, (rules.max_stop_loss_distance || 0) - 0.005))}>-</button>
                                    <span>{((rules.max_stop_loss_distance || 0) * 100).toFixed(1)}%</span>
                                    <button onClick={() => setRule('max_stop_loss_distance', Math.min(0.15, (rules.max_stop_loss_distance || 0) + 0.005))}>+</button>
                                </div>
                            </div>
                            <div className="setting-row">
                                <div>
                                    <div className="sr-label">Min Risk-Reward Ratio</div>
                                    <div className="sr-desc">Minimum target reward relative to stop loss risk (1:X)</div>
                                </div>
                                <div className="number-input">
                                    <button onClick={() => setRule('min_risk_reward_ratio', Math.max(1.0, (rules.min_risk_reward_ratio || 0) - 0.1))}>-</button>
                                    <span>1:{(rules.min_risk_reward_ratio || 0).toFixed(1)}</span>
                                    <button onClick={() => setRule('min_risk_reward_ratio', Math.min(5.0, (rules.min_risk_reward_ratio || 0) + 0.1))}>+</button>
                                </div>
                            </div>
                            <div className="setting-row">
                                <div>
                                    <div className="sr-label">Max Consecutive Losses</div>
                                    <div className="sr-desc">Consecutive losing trades today before locking out model</div>
                                </div>
                                <div className="number-input">
                                    <button onClick={() => setRule('max_consecutive_losses', Math.max(1, (rules.max_consecutive_losses || 0) - 1))}>-</button>
                                    <span>{rules.max_consecutive_losses || 0}</span>
                                    <button onClick={() => setRule('max_consecutive_losses', Math.min(10, (rules.max_consecutive_losses || 0) + 1))}>+</button>
                                </div>
                            </div>
                            <div className="setting-row">
                                <div>
                                    <div className="sr-label">Max Daily Trades Per Stock</div>
                                    <div className="sr-desc">Limit on number of trades on the same stock per model daily</div>
                                </div>
                                <div className="number-input">
                                    <button onClick={() => setRule('max_trades_per_stock_daily', Math.max(1, (rules.max_trades_per_stock_daily || 0) - 1))}>-</button>
                                    <span>{rules.max_trades_per_stock_daily || 0}</span>
                                    <button onClick={() => setRule('max_trades_per_stock_daily', Math.min(20, (rules.max_trades_per_stock_daily || 0) + 1))}>+</button>
                                </div>
                            </div>
                            <div className="setting-row">
                                <div>
                                    <div className="sr-label">Allowed Entry Hours (IST)</div>
                                    <div className="sr-desc">Allowed entry hours (start to end hour)</div>
                                </div>
                                <div className="number-input" style={{ gap: '4px' }}>
                                    <button onClick={() => setRule('entry_start_hour', Math.max(9.0, (rules.entry_start_hour || 0) - 0.25))}>-</button>
                                    <span>
                                        {Math.floor(rules.entry_start_hour || 0)}:
                                        {(((rules.entry_start_hour || 0) % 1) * 60 === 0) ? '00' : '15'}
                                    </span>
                                    <button onClick={() => setRule('entry_start_hour', Math.min(11.0, (rules.entry_start_hour || 0) + 0.25))}>+</button>
                                    <span style={{ margin: '0 4px' }}>to</span>
                                    <button onClick={() => setRule('entry_end_hour', Math.max(12.0, (rules.entry_end_hour || 0) - 0.25))}>-</button>
                                    <span>
                                        {Math.floor(rules.entry_end_hour || 0)}:
                                        {(((rules.entry_end_hour || 0) % 1) * 60 === 0) ? '00' : '15'}
                                    </span>
                                    <button onClick={() => setRule('entry_end_hour', Math.min(15.25, (rules.entry_end_hour || 0) + 0.25))}>+</button>
                                </div>
                            </div>
                            <div className="setting-row">
                                <div>
                                    <div className="sr-label">Enable Futures & Options (F&O)</div>
                                    <div className="sr-desc">Allow agents to trade option premiums (CE/PE) and index futures</div>
                                </div>
                                <ToggleSwitch value={rules.enable_fno_trading !== false} onChange={v => setRule('enable_fno_trading', v)} />
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

                {/* Platform Reset & Capital Configuration */}
                <div className="card settings-card" style={{ borderColor: 'rgba(239, 68, 68, 0.2)' }}>
                    <h3 className="section-title" style={{ color: '#ef4444' }}><Trash2 size={16} /> Platform Reset & Capital Setup</h3>
                    <div className="settings-rows">
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Starting Capital per Agent</div>
                                <div className="sr-desc">Set starting balance (INR) to allocate to each model on reset</div>
                            </div>
                            <div className="number-input" style={{ gap: '6px' }}>
                                <button onClick={() => setRule('starting_capital_per_agent', Math.max(100000, (rules.starting_capital_per_agent || 5000000) - 500000))}>-</button>
                                <span style={{ fontWeight: 'bold' }}>₹{((rules.starting_capital_per_agent || 5000000) / 100000).toFixed(0)} Lakh</span>
                                <button onClick={() => setRule('starting_capital_per_agent', Math.min(100000000, (rules.starting_capital_per_agent || 5000000) + 500000))}>+</button>
                            </div>
                        </div>
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Reset Database & Re-initialize</div>
                                <div className="sr-desc" style={{ color: 'var(--text-secondary)' }}>
                                    Warning: This will permanently delete all trades, positions, and logs. Balances will be reset to ₹{(rules.starting_capital_per_agent || 5000000).toLocaleString()}.
                                </div>
                            </div>
                            <button className="btn-primary" onClick={async () => {
                                const confirmReset = window.confirm("WARNING: Are you absolutely sure you want to reset the platform? This will delete all trade history and agent positions permanently.");
                                if (!confirmReset) return;
                                
                                const loadingToast = toast.loading("Resetting platform and applying starting capital...");
                                try {
                                    const res = await api.post('/settings/reset', {
                                        starting_capital: rules.starting_capital_per_agent || 5000000
                                    });
                                    toast.success(res.data?.message || "Platform reset successfully!", { id: loadingToast });
                                    setTimeout(() => window.location.reload(), 1500);
                                } catch (e) {
                                    console.error(e);
                                    toast.error(e.response?.data?.detail || "Failed to reset database.", { id: loadingToast });
                                }
                            }} style={{ backgroundColor: '#ef4444', color: 'white', padding: '8px 16px', fontWeight: 'bold' }}>
                                Reset Platform
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Settings;
