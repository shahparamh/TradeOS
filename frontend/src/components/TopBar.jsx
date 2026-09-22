import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Zap, Search, LogOut } from 'lucide-react';
import { marketAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { NIFTY50_SYMBOLS, SEARCH_PAGES } from '../utils/symbols';

const TopBar = () => {
    const navigate = useNavigate();
    const { user, logout } = useAuth();
    const [indices, setIndices] = useState([]);
    const [query, setQuery] = useState('');
    const [open, setOpen] = useState(false);
    const [activeIdx, setActiveIdx] = useState(0);
    const inputRef = useRef(null);

    useEffect(() => {
        const fetchIndices = () => {
            marketAPI.getIndices().then(res => setIndices(res.data || [])).catch(() => {});
        };
        fetchIndices();
        const interval = setInterval(fetchIndices, 30000);
        return () => clearInterval(interval);
    }, []);

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
        const symbolMatches = NIFTY50_SYMBOLS
            .filter(s => s.includes(q))
            .slice(0, 6)
            .map(s => ({ type: 'symbol', label: s, meta: 'NSE Equity', value: s }));
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

    const now = new Date();
    const istHour = (now.getUTCHours() + 5 + Math.floor((now.getUTCMinutes() + 30) / 60)) % 24;
    const istMinute = (now.getUTCMinutes() + 30) % 60;
    const dayOfWeek = now.getUTCDay();
    const marketOpen = dayOfWeek >= 1 && dayOfWeek <= 5 &&
        (istHour > 9 || (istHour === 9 && istMinute >= 15)) &&
        (istHour < 15 || (istHour === 15 && istMinute <= 30));

    return (
        <header className="topbar">
            <div className="topbar-brand">
                <Zap size={18} className="logo-icon" fill="currentColor" />
                <h1 className="logo-text">Trade<span>OS</span></h1>
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
                {indices.map(idx => {
                    const pct = idx.percent_change || 0;
                    return (
                        <div className="topbar-ticker-item" key={idx.symbol}>
                            <span className="tt-name">{idx.symbol}</span>
                            <span className="tt-price">{idx.price?.toLocaleString('en-IN')}</span>
                            <span className={`tt-change ${pct >= 0 ? 'up' : 'down'}`}>
                                {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                            </span>
                        </div>
                    );
                })}
            </div>

            <div className="topbar-session">
                <span className={`status-dot ${marketOpen ? 'online' : 'closed'}`}></span>
                NSE {marketOpen ? 'OPEN' : 'CLOSED'}
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
