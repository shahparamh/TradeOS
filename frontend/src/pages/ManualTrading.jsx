import React, { useState, useEffect, useRef } from 'react';
import { Shield, Sparkles, Send, DollarSign, Activity, ChevronRight, Zap } from 'lucide-react';
import toast from 'react-hot-toast';
import { brokerAPI, agentAPI } from '../services/api';

// Predefined searchable list of Indian equities and indices
const SUGGESTION_POOL = [
    { ticker: '^NSEI', name: 'NIFTY 50 Index' },
    { ticker: '^NSEBANK', name: 'NIFTY BANK Index' },
    { ticker: 'RELIANCE.NS', name: 'Reliance Industries Ltd' },
    { ticker: 'TCS.NS', name: 'Tata Consultancy Services Ltd' },
    { ticker: 'INFY.NS', name: 'Infosys Ltd' },
    { ticker: 'SBIN.NS', name: 'State Bank of India' },
    { ticker: 'HDFCBANK.NS', name: 'HDFC Bank Ltd' },
    { ticker: 'ICICIBANK.NS', name: 'ICICI Bank Ltd' },
    { ticker: 'AXISBANK.NS', name: 'Axis Bank Ltd' },
    { ticker: 'KOTAKBANK.NS', name: 'Kotak Mahindra Bank Ltd' },
    { ticker: 'BHARTIARTL.NS', name: 'Bharti Airtel Ltd' },
    { ticker: 'ITC.NS', name: 'ITC Ltd' },
    { ticker: 'LT.NS', name: 'Larsen & Toubro Ltd' },
    { ticker: 'TATASTEEL.NS', name: 'Tata Steel Ltd' },
    { ticker: 'TATAMOTORS.NS', name: 'Tata Motors Ltd' },
    { ticker: 'WIPRO.NS', name: 'Wipro Ltd' },
    { ticker: 'BAJFINANCE.NS', name: 'Bajaj Finance Ltd' },
    { ticker: 'MARUTI.NS', name: 'Maruti Suzuki India Ltd' },
    { ticker: 'SUNPHARMA.NS', name: 'Sun Pharmaceutical Industries Ltd' },
    { ticker: 'NTPC.NS', name: 'NTPC Ltd' },
    { ticker: 'ONGC.NS', name: 'Oil & Natural Gas Corporation Ltd' },
    { ticker: 'COALINDIA.NS', name: 'Coal India Ltd' },
    { ticker: 'HCLTECH.NS', name: 'HCL Technologies Ltd' },
    { ticker: 'TECHM.NS', name: 'Tech Mahindra Ltd' },
    { ticker: 'TITAN.NS', name: 'Titan Company Ltd' },
    { ticker: 'ADANIENT.NS', name: 'Adani Enterprises Ltd' },
    { ticker: 'ADANIPORTS.NS', name: 'Adani Ports & Special Economic Zone' },
    { ticker: 'BPCL.NS', name: 'Bharat Petroleum Corporation Ltd' },
    { ticker: 'GRASIM.NS', name: 'Grasim Industries Ltd' },
    { ticker: 'NESTLEIND.NS', name: 'Nestle India Ltd' },
    { ticker: 'ULTRACEMCO.NS', name: 'UltraTech Cement Ltd' },
    { ticker: 'HINDUNILVR.NS', name: 'Hindustan Unilever Ltd' },
    { ticker: 'ANANTRAJ.NS', name: 'Anant Raj Ltd' },
    { ticker: 'RCF.NS', name: 'Rashtriya Chemicals & Fertilizers Ltd' },
    { ticker: 'PGEL.NS', name: 'PG Electroplast Ltd' },
    { ticker: 'LTM.NS', name: 'L&T Technology Services Ltd' },
    { ticker: 'HFCL.NS', name: 'HFCL Ltd' },
    { ticker: 'BSE.NS', name: 'BSE Ltd' },
];

const ManualTrading = () => {
    const [agents, setAgents] = useState([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);

    // Form states
    const [formData, setFormData] = useState({
        agent_id: '',
        symbol: '',
        action: 'BUY',
        quantity: 10,
        trade_type: 'INTRADAY',
        position_type: 'LONG',
        stop_loss: 0,
        target_price: 0
    });

    const [suggestions, setSuggestions] = useState([]);
    const [showSuggestions, setShowSuggestions] = useState(false);
    const suggestionRef = useRef(null);

    useEffect(() => {
        const fetchAgents = async () => {
            try {
                const res = await brokerAPI.getLeaderboard();
                setAgents(res.data || []);
                if (res.data && res.data.length > 0) {
                    setFormData(prev => ({ ...prev, agent_id: res.data[0].id }));
                }
            } catch (err) {
                console.error(err);
                toast.error("Failed to load active agents list.");
            } finally {
                setLoading(false);
            }
        };
        fetchAgents();
    }, []);

    // Close suggestions on outside click
    useEffect(() => {
        const handleOutsideClick = (e) => {
            if (suggestionRef.current && !suggestionRef.current.contains(e.target)) {
                setShowSuggestions(false);
            }
        };
        document.addEventListener('mousedown', handleOutsideClick);
        return () => document.removeEventListener('mousedown', handleOutsideClick);
    }, []);

    const handleSymbolChange = (val) => {
        const uppercaseVal = val.toUpperCase();
        setFormData(prev => ({ ...prev, symbol: uppercaseVal }));

        if (!val) {
            setSuggestions([]);
            setShowSuggestions(false);
            return;
        }

        const filtered = SUGGESTION_POOL.filter(item => 
            item.ticker.includes(uppercaseVal) || 
            item.name.toUpperCase().includes(uppercaseVal)
        );
        setSuggestions(filtered);
        setShowSuggestions(true);
    };

    const handleSelectSuggestion = (ticker) => {
        setFormData(prev => ({ ...prev, symbol: ticker }));
        setShowSuggestions(false);
    };

    // Dynamically adjust position type when trade type changes
    const handleTradeTypeChange = (type) => {
        let positionType = 'LONG';
        if (type === 'OPTIONS') {
            positionType = formData.action === 'BUY' ? 'BUY_CE' : 'SELL_CE';
        } else {
            positionType = formData.action === 'BUY' ? 'LONG' : 'SHORT';
        }
        setFormData(prev => ({
            ...prev,
            trade_type: type,
            position_type: positionType
        }));
    };

    const handleActionChange = (action) => {
        let positionType = 'LONG';
        if (formData.trade_type === 'OPTIONS') {
            positionType = action === 'BUY' ? 'BUY_CE' : 'SELL_CE';
        } else {
            positionType = action === 'BUY' ? 'LONG' : 'SHORT';
        }
        setFormData(prev => ({
            ...prev,
            action: action,
            position_type: positionType
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!formData.agent_id) {
            toast.error("Please select an agent.");
            return;
        }
        if (!formData.symbol) {
            toast.error("Please enter or select a stock symbol.");
            return;
        }
        if (formData.quantity <= 0) {
            toast.error("Quantity must be greater than 0.");
            return;
        }

        setSubmitting(true);
        const submitToast = toast.loading("Submitting manual trade request to Virtual Broker...");
        try {
            const res = await brokerAPI.placeManualTrade({
                agent_id: parseInt(formData.agent_id),
                symbol: formData.symbol,
                action: formData.action,
                quantity: parseInt(formData.quantity),
                trade_type: formData.trade_type,
                position_type: formData.position_type,
                stop_loss: parseFloat(formData.stop_loss || 0),
                target_price: parseFloat(formData.target_price || 0)
            });
            toast.success(res.data.message || "Manual trade executed successfully!", { id: submitToast });
            
            // Clear inputs
            setFormData(prev => ({
                ...prev,
                symbol: '',
                stop_loss: 0,
                target_price: 0
            }));
            
            // Refresh agents leaderboard for balance updates
            const agentRes = await brokerAPI.getLeaderboard();
            setAgents(agentRes.data || []);
        } catch (err) {
            console.error(err);
            toast.error(err.response?.data?.detail || "Failed to execute trade.", { id: submitToast });
        } finally {
            setSubmitting(false);
        }
    };

    const activeAgent = agents.find(a => a.id === parseInt(formData.agent_id));

    if (loading) return <div className="page-loading">Initializing manual terminal connection...</div>;

    return (
        <div className="manual-trading-page animate-fade-in" style={{ maxWidth: '900px', margin: '0 auto' }}>
            <header className="page-header">
                <div>
                    <h1>Manual Trading Panel</h1>
                    <p className="subtitle">Execute manual override trades on behalf of agent balances</p>
                </div>
            </header>

            <div className="settings-grid" style={{ gridTemplateColumns: '1fr 1.2fr', gap: '24px' }}>
                {/* Form column */}
                <div className="card settings-card" style={{ padding: '24px', overflow: 'visible' }}>
                    <h3 className="section-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Send size={16} color="var(--accent-blue)" /> Trade Ticket
                    </h3>

                    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        {/* Select Agent */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: 'var(--text-secondary)' }}>Trading Account (Agent)</label>
                            <select 
                                value={formData.agent_id} 
                                onChange={e => setFormData(prev => ({ ...prev, agent_id: e.target.value }))}
                                style={{
                                    background: 'var(--bg-tertiary)',
                                    border: '1px solid var(--border-color)',
                                    color: 'var(--text-primary)',
                                    padding: '10px',
                                    borderRadius: '8px',
                                    outline: 'none',
                                    width: '100%',
                                    fontWeight: '600'
                                }}
                            >
                                {agents.map(agent => (
                                    <option key={agent.id} value={agent.id}>
                                        {agent.name} (Bal: ₹{agent.cash_balance.toLocaleString(undefined, { maximumFractionDigits: 0 })})
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Action Buttons (BUY/SELL) */}
                        <div style={{ display: 'flex', gap: '10px' }}>
                            <button
                                type="button"
                                onClick={() => handleActionChange('BUY')}
                                style={{
                                    flex: 1,
                                    padding: '12px',
                                    border: '1px solid',
                                    borderColor: formData.action === 'BUY' ? 'var(--green-profit)' : 'var(--border-color)',
                                    background: formData.action === 'BUY' ? 'rgba(16, 185, 129, 0.12)' : 'transparent',
                                    color: formData.action === 'BUY' ? 'var(--green-profit)' : 'var(--text-secondary)',
                                    borderRadius: '8px',
                                    fontWeight: 'bold',
                                    cursor: 'pointer',
                                    transition: 'all 0.15s'
                                }}
                            >
                                BUY (LONG)
                            </button>
                            <button
                                type="button"
                                onClick={() => handleActionChange('SELL')}
                                style={{
                                    flex: 1,
                                    padding: '12px',
                                    border: '1px solid',
                                    borderColor: formData.action === 'SELL' ? 'var(--red-loss)' : 'var(--border-color)',
                                    background: formData.action === 'SELL' ? 'rgba(239, 68, 68, 0.12)' : 'transparent',
                                    color: formData.action === 'SELL' ? 'var(--red-loss)' : 'var(--text-secondary)',
                                    borderRadius: '8px',
                                    fontWeight: 'bold',
                                    cursor: 'pointer',
                                    transition: 'all 0.15s'
                                }}
                            >
                                SELL (SHORT)
                            </button>
                        </div>

                        {/* Symbol Input with Autocomplete suggestions dropdown */}
                        <div ref={suggestionRef} style={{ display: 'flex', flexDirection: 'column', gap: '6px', position: 'relative' }}>
                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: 'var(--text-secondary)' }}>Stock Symbol</label>
                            <input 
                                type="text"
                                placeholder="Type to search (e.g. RELIANCE, TCS, NIFTY)"
                                value={formData.symbol}
                                onChange={e => handleSymbolChange(e.target.value)}
                                onFocus={() => formData.symbol && setShowSuggestions(true)}
                                style={{
                                    background: 'var(--bg-tertiary)',
                                    border: '1px solid var(--border-color)',
                                    color: 'var(--text-primary)',
                                    padding: '10px',
                                    borderRadius: '8px',
                                    outline: 'none',
                                    fontWeight: '600'
                                }}
                            />
                            
                            {/* Suggestions Dropdown */}
                            {showSuggestions && suggestions.length > 0 && (
                                <div style={{
                                    position: 'absolute',
                                    top: '100%',
                                    left: 0,
                                    right: 0,
                                    background: '#1a2332',
                                    border: '1px solid var(--border-color)',
                                    borderRadius: '8px',
                                    marginTop: '4px',
                                    maxHeight: '180px',
                                    overflowY: 'auto',
                                    zIndex: 1000,
                                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)'
                                }}>
                                    {suggestions.map((item) => (
                                        <div
                                            key={item.ticker}
                                            onClick={() => handleSelectSuggestion(item.ticker)}
                                            style={{
                                                padding: '10px 14px',
                                                cursor: 'pointer',
                                                borderBottom: '1px solid rgba(255,255,255,0.03)',
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                alignItems: 'center',
                                                fontSize: '13px'
                                            }}
                                            onMouseEnter={(e) => e.target.style.background = '#2563eb'}
                                            onMouseLeave={(e) => e.target.style.background = 'transparent'}
                                        >
                                            <span style={{ fontWeight: 'bold', color: '#ffffff' }}>{item.ticker}</span>
                                            <span style={{ fontSize: '11px', color: '#94a3b8' }}>{item.name}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Trade Type selection */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: 'var(--text-secondary)' }}>Segment Type</label>
                            <div style={{ display: 'flex', gap: '8px' }}>
                                {['INTRADAY', 'FUTURES', 'OPTIONS'].map(type => (
                                    <button
                                        key={type}
                                        type="button"
                                        onClick={() => handleTradeTypeChange(type)}
                                        style={{
                                            flex: 1,
                                            padding: '8px',
                                            border: '1px solid',
                                            borderColor: formData.trade_type === type ? 'var(--accent-blue)' : 'var(--border-color)',
                                            background: formData.trade_type === type ? 'rgba(59, 130, 246, 0.1)' : 'var(--bg-secondary)',
                                            color: formData.trade_type === type ? 'var(--accent-blue)' : 'var(--text-secondary)',
                                            borderRadius: '6px',
                                            fontSize: '11px',
                                            fontWeight: 'bold',
                                            cursor: 'pointer',
                                            transition: 'all 0.15s'
                                        }}
                                    >
                                        {type}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Position Type Selector depending on trade type */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: 'var(--text-secondary)' }}>Position Type</label>
                            <select 
                                value={formData.position_type}
                                onChange={e => setFormData(prev => ({ ...prev, position_type: e.target.value }))}
                                style={{
                                    background: 'var(--bg-tertiary)',
                                    border: '1px solid var(--border-color)',
                                    color: 'var(--text-primary)',
                                    padding: '10px',
                                    borderRadius: '8px',
                                    outline: 'none',
                                    fontWeight: '600'
                                }}
                            >
                                {formData.trade_type === 'OPTIONS' ? (
                                    formData.action === 'BUY' ? (
                                        <>
                                            <option value="BUY_CE">BUY CALL (CE)</option>
                                            <option value="BUY_PE">BUY PUT (PE)</option>
                                        </>
                                    ) : (
                                        <>
                                            <option value="SELL_CE">WRITE CALL (CE)</option>
                                            <option value="SELL_PE">WRITE PUT (PE)</option>
                                        </>
                                    )
                                ) : (
                                    formData.action === 'BUY' ? (
                                        <option value="LONG">LONG</option>
                                    ) : (
                                        <option value="SHORT">SHORT</option>
                                    )
                                )}
                            </select>
                        </div>

                        {/* Quantity and SL/TP fields */}
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <label style={{ fontSize: '12px', fontWeight: 'bold', color: 'var(--text-secondary)' }}>Quantity (Lots/Shares)</label>
                                <input 
                                    type="number"
                                    min="1"
                                    value={formData.quantity}
                                    onChange={e => setFormData(prev => ({ ...prev, quantity: Math.max(1, parseInt(e.target.value) || 0) }))}
                                    style={{
                                        background: 'var(--bg-tertiary)',
                                        border: '1px solid var(--border-color)',
                                        color: 'var(--text-primary)',
                                        padding: '10px',
                                        borderRadius: '8px',
                                        outline: 'none',
                                        fontWeight: '600'
                                    }}
                                />
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                <label style={{ fontSize: '12px', fontWeight: 'bold', color: 'var(--text-secondary)' }}>Stop Loss (SL ₹)</label>
                                <input 
                                    type="number"
                                    step="0.05"
                                    placeholder="0 (Disabled)"
                                    value={formData.stop_loss}
                                    onChange={e => setFormData(prev => ({ ...prev, stop_loss: parseFloat(e.target.value) || 0 }))}
                                    style={{
                                        background: 'var(--bg-tertiary)',
                                        border: '1px solid var(--border-color)',
                                        color: 'var(--text-primary)',
                                        padding: '10px',
                                        borderRadius: '8px',
                                        outline: 'none',
                                        fontWeight: '600'
                                    }}
                                />
                            </div>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            <label style={{ fontSize: '12px', fontWeight: 'bold', color: 'var(--text-secondary)' }}>Target Profit (Target ₹)</label>
                            <input 
                                type="number"
                                step="0.05"
                                placeholder="0 (Disabled)"
                                value={formData.target_price}
                                onChange={e => setFormData(prev => ({ ...prev, target_price: parseFloat(e.target.value) || 0 }))}
                                style={{
                                    background: 'var(--bg-tertiary)',
                                    border: '1px solid var(--border-color)',
                                    color: 'var(--text-primary)',
                                    padding: '10px',
                                    borderRadius: '8px',
                                    outline: 'none',
                                    fontWeight: '600'
                                }}
                            />
                        </div>

                        <button 
                            type="submit" 
                            disabled={submitting} 
                            style={{
                                background: formData.action === 'BUY' ? 'var(--green-profit)' : 'var(--red-loss)',
                                color: 'white',
                                padding: '12px',
                                border: 'none',
                                borderRadius: '8px',
                                fontWeight: 'bold',
                                fontSize: '14px',
                                cursor: 'pointer',
                                transition: 'all 0.2s',
                                marginTop: '10px'
                            }}
                        >
                            {submitting ? 'Executing trade...' : `EXECUTE ${formData.action}`}
                        </button>
                    </form>
                </div>

                {/* Account Details card */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                    <div className="card settings-card" style={{ padding: '24px' }}>
                        <h3 className="section-title"><DollarSign size={16} /> Account Metrics</h3>
                        
                        {activeAgent ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                                <div style={{ display: 'flex', justifycontent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '10px' }}>
                                    <span style={{ color: 'var(--text-muted)' }}>Account Holder:</span>
                                    <span style={{ fontWeight: 'bold' }}>{activeAgent.name}</span>
                                </div>
                                <div style={{ display: 'flex', justifycontent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '10px' }}>
                                    <span style={{ color: 'var(--text-muted)' }}>Engine Version:</span>
                                    <span>{activeAgent.model_name}</span>
                                </div>
                                <div style={{ display: 'flex', justifycontent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '10px' }}>
                                    <span style={{ color: 'var(--text-muted)' }}>Available Margin (Cash):</span>
                                    <span style={{ fontWeight: 'bold', color: 'var(--accent-blue)', fontFamily: 'var(--font-mono)' }}>
                                        ₹{activeAgent.cash_balance.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                    </span>
                                </div>
                                <div style={{ display: 'flex', justifycontent: 'space-between', borderBottom: '1px solid rgba(255,255,255,0.05)', paddingBottom: '10px' }}>
                                    <span style={{ color: 'var(--text-muted)' }}>Total Realized PnL:</span>
                                    <span style={{ fontWeight: 'bold', fontFamily: 'var(--font-mono)' }} className={activeAgent.total_pnl >= 0 ? 'text-profit' : 'text-loss'}>
                                        {activeAgent.total_pnl >= 0 ? '+' : ''}₹{activeAgent.total_pnl.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                                    </span>
                                </div>
                            </div>
                        ) : (
                            <div className="empty-state">Select an account to view metrics</div>
                        )}
                    </div>

                    <div className="card settings-card" style={{ padding: '24px' }}>
                        <h3 className="section-title"><Activity size={16} /> Brokerage Specifications</h3>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                            <p>💰 **Brokerage Cost**: 0.03% on filled trade premium value.</p>
                            <p>⚡ **Execution Slippage**: 0.05% applied to market orders (long buys filled higher; short sells filled lower).</p>
                            <p>📊 **F&O Lot Multipliers**: Index Options & Futures follow NSE lot conventions (Nifty lot: 50, Bank Nifty lot: 15).</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default ManualTrading;
