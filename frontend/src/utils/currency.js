import { MARKETS } from '../context/MarketContext';

/** Formats an amount using the given market's currency/locale conventions.
 * Defaults to IN/INR for any existing call site that hasn't been updated with a market yet. */
export function formatCurrency(amount, market = 'IN', opts = {}) {
    const meta = MARKETS[market] || MARKETS.IN;
    const locale = market === 'US' ? 'en-US' : 'en-IN';
    const value = Number(amount) || 0;
    const formatted = value.toLocaleString(locale, {
        minimumFractionDigits: opts.minimumFractionDigits ?? 2,
        maximumFractionDigits: opts.maximumFractionDigits ?? 2,
    });
    return `${meta.currencySymbol}${formatted}`;
}

export function currencySymbol(market = 'IN') {
    return (MARKETS[market] || MARKETS.IN).currencySymbol;
}
