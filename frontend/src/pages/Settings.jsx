import React, { useState } from 'react';
import { Settings as SettingsIcon, Key, Shield, Bell, Zap, Database, Save, CheckCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../services/api';

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
        maxTrades: 3,
        maxPositions: 5,
        capitalPerTrade: 20,
    });

    const handleSave = () => {
        toast.success('Configuration saved successfully!');
    };

    const set = (key, val) => setConfig(prev => ({ ...prev, [key]: val }));

    return (
        <div className="settings-page animate-fade-in">
            <header className="page-header">
                <div>
                    <h1>System Settings</h1>
                    <p className="subtitle">Configure trading parameters and system behavior</p>
                </div>
                <button className="btn-primary" onClick={handleSave}>
                    <Save size={15} /> Save Configuration
                </button>
            </header>

            <div className="settings-grid">
                {/* Trading Rules */}
                <div className="card settings-card">
                    <h3 className="section-title"><Shield size={16} /> Risk Management</h3>
                    <div className="settings-rows">
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Auto Square-Off at 3:15 PM</div>
                                <div className="sr-desc">Automatically close all positions before market close</div>
                            </div>
                            <ToggleSwitch value={config.autoSquareOff} onChange={v => set('autoSquareOff', v)} />
                        </div>
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Risk Alerts</div>
                                <div className="sr-desc">Show warnings when positions approach stop-loss</div>
                            </div>
                            <ToggleSwitch value={config.riskAlerts} onChange={v => set('riskAlerts', v)} />
                        </div>
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Max Intraday Trades</div>
                                <div className="sr-desc">Per agent, per day limit</div>
                            </div>
                            <div className="number-input">
                                <button onClick={() => set('maxTrades', Math.max(1, config.maxTrades - 1))}>-</button>
                                <span>{config.maxTrades}</span>
                                <button onClick={() => set('maxTrades', Math.min(10, config.maxTrades + 1))}>+</button>
                            </div>
                        </div>
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Max Open Positions</div>
                                <div className="sr-desc">Across all agents simultaneously</div>
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
                                <div className="sr-desc">Max % of agent balance per trade</div>
                            </div>
                            <div className="number-input">
                                <button onClick={() => set('capitalPerTrade', Math.max(5, config.capitalPerTrade - 5))}>-</button>
                                <span>{config.capitalPerTrade}%</span>
                                <button onClick={() => set('capitalPerTrade', Math.min(50, config.capitalPerTrade + 5))}>+</button>
                            </div>
                        </div>
                    </div>
                </div>

                {/* AI Agents */}
                <div className="card settings-card">
                    <h3 className="section-title"><Zap size={16} /> AI Agents</h3>
                    <div className="settings-rows">
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Gemini Flash</div>
                                <div className="sr-desc">Google's Gemini 2.0 Flash model</div>
                            </div>
                            <ToggleSwitch value={config.geminiEnabled} onChange={v => set('geminiEnabled', v)} />
                        </div>
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Groq-Llama 70B</div>
                                <div className="sr-desc">Meta's LLaMA 3.3 on Groq (fast inference)</div>
                            </div>
                            <ToggleSwitch value={config.groqEnabled} onChange={v => set('groqEnabled', v)} />
                        </div>
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Scan Interval</div>
                                <div className="sr-desc">Minutes between market scans</div>
                            </div>
                            <div className="number-input">
                                <button onClick={() => set('scanInterval', Math.max(1, config.scanInterval - 1))}>-</button>
                                <span>{config.scanInterval} min</span>
                                <button onClick={() => set('scanInterval', Math.min(60, config.scanInterval + 1))}>+</button>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Notifications */}
                <div className="card settings-card">
                    <h3 className="section-title"><Bell size={16} /> Notifications</h3>
                    <div className="settings-rows">
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Email Alerts</div>
                                <div className="sr-desc">Receive trade notifications via email</div>
                            </div>
                            <ToggleSwitch value={config.emailNotif} onChange={v => set('emailNotif', v)} />
                        </div>
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Sound Alerts</div>
                                <div className="sr-desc">Play audio when trades are executed</div>
                            </div>
                            <ToggleSwitch value={config.voiceAlerts} onChange={v => set('voiceAlerts', v)} />
                        </div>
                    </div>
                </div>

                {/* System Info */}
                <div className="card settings-card">
                    <h3 className="section-title"><Database size={16} /> System Info</h3>
                    <div className="settings-rows">
                        <div className="info-row">
                            <span>Database</span>
                            <span className="text-profit">● Connected (SQLite)</span>
                        </div>
                        <div className="info-row">
                            <span>Backend</span>
                            <span className="text-profit">● Running on :8000</span>
                        </div>
                        <div className="info-row">
                            <span>TradeOS Version</span>
                            <span>Phase 7 — v1.1.0</span>
                        </div>
                        <div className="info-row">
                            <span>Trading Mode</span>
                            <span className="badge-pill info">Paper Trading</span>
                        </div>
                    </div>
                </div>

                {/* System Automation (Phase 7) */}
                <div className="card settings-card">
                    <h3 className="section-title"><Database size={16} /> System Automation</h3>
                    <div className="settings-rows">
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Trading Loop</div>
                                <div className="sr-desc">Next run: Mon 9:15 AM IST</div>
                            </div>
                            <button className="btn-primary" onClick={async () => {
                                try {
                                    await api.post('/scheduler/trigger');
                                    toast.success('Main trading cycle triggered in background');
                                } catch (e) { toast.error('Failed to trigger cycle'); }
                            }} style={{ padding: '6px 12px', fontSize: '11px' }}>
                                Trigger Now
                            </button>
                        </div>
                        <div className="setting-row">
                            <div>
                                <div className="sr-label">Position Monitor</div>
                                <div className="sr-desc">Check all SL/TP hits manually</div>
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
