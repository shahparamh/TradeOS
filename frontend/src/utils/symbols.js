// Shared NSE symbol list for the global instrument search and the Market heatmap.
// Kept as plain tickers (no .NS suffix) — callers append it where the backend expects it.
export const NIFTY50_SYMBOLS = [
  'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK',
  'SBIN', 'HINDUNILVR', 'BHARTIARTL', 'ITC', 'KOTAKBANK',
  'LT', 'AXISBANK', 'WIPRO', 'BAJFINANCE', 'MARUTI',
  'NTPC', 'POWERGRID', 'SUNPHARMA', 'TITAN', 'TECHM',
  'HCLTECH', 'ULTRACEMCO', 'ADANIENT', 'ADANIPORTS', 'COALINDIA',
  'ONGC', 'BPCL', 'GRASIM', 'NESTLEIND', 'TATASTEEL',
];

// Static page destinations surfaced by the global search alongside instrument matches.
export const SEARCH_PAGES = [
  { label: 'Dashboard', path: '/' },
  { label: 'Pre-Market Strategy', path: '/pre-market' },
  { label: 'Live Positions', path: '/positions' },
  { label: 'Trade History', path: '/history' },
  { label: 'Survival Arena', path: '/arena' },
  { label: 'Market Heatmap', path: '/market' },
  { label: 'Settings', path: '/settings' },
];
