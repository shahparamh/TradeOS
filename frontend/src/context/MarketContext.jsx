import React, { createContext, useState, useContext, useCallback } from 'react';

const MarketContext = createContext(null);

const STORAGE_KEY = 'tradeos_market';

export const MARKETS = {
    IN: { code: 'IN', label: 'India (NSE)', flag: '🇮🇳', currency: 'INR', currencySymbol: '₹', exchange: 'NSE', timezone: 'Asia/Kolkata' },
    US: { code: 'US', label: 'United States', flag: '🇺🇸', currency: 'USD', currencySymbol: '$', exchange: 'NASDAQ/NYSE', timezone: 'America/New_York' },
};

function readStoredMarket() {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        return stored === 'US' ? 'US' : 'IN';
    } catch {
        return 'IN';
    }
}

export const MarketProvider = ({ children }) => {
    const [market, setMarketState] = useState(readStoredMarket);

    const setMarket = useCallback((next) => {
        const normalized = next === 'US' ? 'US' : 'IN';
        setMarketState(normalized);
        try {
            localStorage.setItem(STORAGE_KEY, normalized);
        } catch {
            // ignore storage failures (private browsing, quota, etc.)
        }
    }, []);

    const meta = MARKETS[market];

    return (
        <MarketContext.Provider value={{ market, setMarket, meta }}>
            {children}
        </MarketContext.Provider>
    );
};

export const useMarket = () => {
    const ctx = useContext(MarketContext);
    if (!ctx) throw new Error('useMarket must be used within a MarketProvider');
    return ctx;
};
