import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap, Search, LogOut } from 'lucide-react';
import { marketAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { useMarket, MARKETS } from '../context/MarketContext';
import { NIFTY50_SYMBOLS, SEARCH_PAGES, US_SYMBOLS } from '../utils/symbols';

const TopBar = () => {
    const navigate = useNavigate();
    const { user, logout } = useAuth();
    const { market, setMarket, meta } = useMarket();
    const [indices, setIndices] = useState([]);
    const [marketStatus, setMarketStatus] = useState(null);
    const [query, setQuery] = useState('');
    const [open, setOpen] = useState(false);
    const [activeIdx, setActiveIdx] = useState(0);
    const inputRef = useRef(null);

    // Indices are India-only for now (US index quotes aren't wired into /market/indices yet)
    // — don't show stale Nifty/Sensex numbers when the US market is selected.
    useEffect(() => {
        if (market !== 'IN') {
            setIndices([]);
            return;
        }
        const fetchIndices = () => {
            marketAPI.getIndices().then(res => setIndices(res.data || [])).catch(() => {});
        };
        fetchIndices();
        const interval = setInterval(fetchIndices, 30000);
        return () => clearInterval(interval);
    }, [market]);

    useEffect(() => {
        const fetchStatus = () => {
            marketAPI.getStatus().then(res => setMarketStatus(res.data)).catch(() => setMarketStatus(null));
        };
        fetchStatus();
        const interval = setInterval(fetchStatus, 30000);
        return () => clearInterval(interval);
    }, [market]);

    // Cmd/Ctrl+K opens and focuses global search; Escape closes it.
    useEffect(() => {
        const handleKeyDown = (e) => {
            const tag = document.activeElement?.tagName;
            const isEditable = tag === 'INPUT' || tag === 'TEXTAREA' || document.activeElement?.isContentEditable;

            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                setOpen(true);
                inputRef.current?.focus();
            } else if (e.key === 'Escape' && !isEditable) {
                setOpen(false);
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, []);

    const results = query.trim() === '' ? [] : (() => {
        const q = query.trim().toUpperCase();
        const symbolPool = market === 'US' ? US_SYMBOLS : NIFTY50_SYMBOLS;
        const symbolMatches = symbolPool
            .filter(s => s.includes(q))
            .slice(0, 6)
            .map(s => ({ type: 'symbol', label: s, meta: market === 'US' ? 'US Equity' : 'NSE Equity', value: s }));
        const pageMatches = SEARCH_PAGES
            .filter(p => p.label.toUpperCase().includes(q))
            .map(p => ({ type: 'page', label: p.label, meta: 'Page', value: p.path }));
        return [...symbolMatches, ...pageMatches].slice(0, 8);
    })();

    const selectResult = useCallback((result) => {
        if (!result) return;
        if (result.type === 'symbol') {
            navigate(`/market?symbol=${result.value}`);
        } else {
            navigate(result.value);
        }
        setQuery('');
        setOpen(false);
        inputRef.current?.blur();
    }, [navigate]);

    const handleKeyNav = (e) => {
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActiveIdx(i => Math.min(i + 1, results.length - 1));
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActiveIdx(i => Math.max(i - 1, 0));
        } else if (e.key === 'Enter') {
            e.preventDefault();
            selectResult(results[activeIdx]);
        } else if (e.key === 'Escape') {
            setOpen(false);
            inputRef.current?.blur();
        }
    };

    const marketOpen = !!marketStatus?.is_open;

    return (
        <header className="topbar">
            <div className="topbar-brand">
                <Zap size={18} className="logo-icon" fill="currentColor" />
                <h1 className="logo-text">Trade<span>OS</span></h1>
            </div>

            <div className="market-switch" role="group" aria-label="Select market">
                {Object.values(MARKETS).map((m) => (
                    <button
                        key={m.code}
                        type="button"
                        className={`market-switch-btn ${market === m.code ? 'active' : ''}`}
                        onClick={() => setMarket(m.code)}
                        title={m.label}
                    >
                        <span className="market-switch-flag">{m.flag}</span>
                        <span className="market-switch-code">{m.code}</span>
                    </button>
                ))}
            </div>

            <div className="topbar-search">
                <Search size={13} />
                <input
                    ref={inputRef}
                    type="text"
                    placeholder="Search symbol or page..."
                    value={query}
                    onChange={(e) => { setQuery(e.target.value); setActiveIdx(0); }}
                    onFocus={() => setOpen(true)}
                    onBlur={() => setTimeout(() => setOpen(false), 150)}
                    onKeyDown={handleKeyNav}
                    aria-label="Global instrument and page search"
                />
                {!query && <span className="kbd-hint">⌘K</span>}
                {open && results.length > 0 && (
                    <div className="topbar-search-results" role="listbox">
                        {results.map((r, i) => (
                            <div
                                key={`${r.type}-${r.label}`}
                                role="option"
                                aria-selected={i === activeIdx}
                                className={`topbar-search-result ${i === activeIdx ? 'active-result' : ''}`}
                                onMouseDown={() => selectResult(r)}
                                onMouseEnter={() => setActiveIdx(i)}
                            >
                                <span className="tsr-label">{r.label}</span>
                                <span className="tsr-meta">{r.meta}</span>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            <div className="topbar-ticker">
                {/* One track, content duplicated back-to-back inside it. Animating this
                    single track from translateX(0) to translateX(-50%) moves it exactly
                    one copy's width — so the duplicate is already in position to take
                    over, and the loop restart is invisible. */}
                <div
                    className="topbar-ticker-track"
                    style={{ '--ticker-duration': `${Math.max(indices.length * 6, 14)}s` }}
                >
                    {[0, 1].map(copy => (
                        indices.map(idx => {
                            const pct = idx.percent_change || 0;
                            return (
                                <div className="topbar-ticker-item" key={`${copy}-${idx.symbol}`} aria-hidden={copy === 1}>
                                    <span className="tt-name">{idx.symbol}</span>
                                    <span className="tt-price">{idx.price?.toLocaleString(market === 'US' ? 'en-US' : 'en-IN')}</span>
                                    <span className={`tt-change ${pct >= 0 ? 'up' : 'down'}`}>
                                        {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                                    </span>
                                </div>
                            );
                        })
                    ))}
                </div>
            </div>

            <div className="topbar-session">
                <span className={`status-dot ${marketOpen ? 'online' : 'closed'}`}></span>
                {meta.exchange} {marketOpen ? 'OPEN' : 'CLOSED'}
            </div>

            {user && (
                <div className="topbar-user">
                    <span className="user-name mono">{user.username}</span>
                    <button className="logout-btn" onClick={logout} title="Sign Out" aria-label="Sign out">
                        <LogOut size={14} />
                    </button>
                </div>
            )}
        </header>
    );
};

export default TopBar;
