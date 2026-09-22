import { useState, useEffect, useCallback } from 'react';
import { Star } from 'lucide-react';
import { marketAPI } from '../services/api';

// Short display names for the backend's tracked watchlist — falls back to the raw symbol.
const DISPLAY_NAMES = {
    'RELIANCE.NS': 'Reliance Industries',
    'HDFCBANK.NS': 'HDFC Bank',
    'SBIN.NS': 'State Bank of India',
    'INFY.NS': 'Infosys',
    'TCS.NS': 'Tata Consultancy Svcs',
    'HCLTECH.NS': 'HCL Technologies',
    'WIPRO.NS': 'Wipro',
    'CIPLA.NS': 'Cipla',
    'VEDL.NS': 'Vedanta',
    'DIVISLAB.NS': "Divi's Laboratories",
    'VBL.NS': 'Varun Beverages',
};

const Watchlist = ({ selectedSymbol, onSelect }) => {
    const [symbols, setSymbols] = useState([]);
    const [quotes, setQuotes] = useState({});
    const [loading, setLoading] = useState(true);

    const fetchQuotes = useCallback(async (syms) => {
        if (!syms.length) return;
        try {
            const res = await marketAPI.getPrices(syms);
            setQuotes(res.data || {});
        } catch (_) {
            // keep last known quotes on a transient failure
        }
    }, []);

    useEffect(() => {
        let interval;
        marketAPI.getWatchlist()
            .then(res => {
                const equitySymbols = (res.data.symbols || []).filter(s => !s.startsWith('^'));
                setSymbols(equitySymbols);
                fetchQuotes(equitySymbols);
                interval = setInterval(() => fetchQuotes(equitySymbols), 30000);
            })
            .catch(() => {})
            .finally(() => setLoading(false));
        return () => clearInterval(interval);
    }, [fetchQuotes]);

    return (
        <div className="card watchlist-panel">
            <div className="panel-title-bar">
                <h3 className="panel-title"><Star size={14} /> Watchlist</h3>
                <span className="panel-meta">{symbols.length} instruments</span>
            </div>

            {loading ? (
                <div className="panel-loading">Loading quotes…</div>
            ) : symbols.length === 0 ? (
                <div className="panel-empty">No watchlist instruments configured.</div>
            ) : (
                <div className="watchlist-rows">
                    {symbols.map(sym => {
                        const q = quotes[sym];
                        const pct = q?.percent_change ?? null;
                        const isSelected = sym === selectedSymbol;
                        return (
                            <button
                                key={sym}
                                className={`watchlist-row ${isSelected ? 'selected' : ''}`}
                                onClick={() => onSelect(sym)}
                            >
                                <div className="wl-identity">
                                    <span className="wl-symbol mono">{sym.replace('.NS', '')}</span>
                                    <span className="wl-name">{DISPLAY_NAMES[sym] || sym}</span>
                                </div>
                                <div className="wl-values">
                                    <span className="wl-price mono">{q ? `₹${q.price.toLocaleString('en-IN')}` : '—'}</span>
                                    <span className={`wl-change mono ${pct == null ? '' : pct >= 0 ? 'up' : 'down'}`}>
                                        {pct == null ? '—' : `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%`}
                                    </span>
                                </div>
                            </button>
                        );
                    })}
                </div>
            )}
        </div>
    );
};

export default Watchlist;
