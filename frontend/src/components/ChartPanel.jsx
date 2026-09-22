import { useState, useEffect, useCallback } from 'react';
import { RefreshCw } from 'lucide-react';
import api from '../services/api';
import CandlestickChart from './CandlestickChart';

const TIMEFRAMES = [
    { key: '1D', interval: '5m', period: '1d' },
    { key: '1W', interval: '5m', period: '5d' },
    { key: '1M', interval: '1h', period: '1mo' },
    { key: '3M', interval: '1d', period: '3mo' },
    { key: '1Y', interval: '1d', period: '1y' },
];

const ChartPanel = ({ symbol, quote }) => {
    const [timeframe, setTimeframe] = useState('1D');
    const [candles, setCandles] = useState([]);
    const [loading, setLoading] = useState(true);

    const fetchCandles = useCallback(async (sym, tf) => {
        if (!sym) return;
        setLoading(true);
        try {
            const { interval, period } = TIMEFRAMES.find(t => t.key === tf);
            const res = await api.get(`/market/candles/${sym}?interval=${interval}&period=${period}`);
            const formatted = (res.data || [])
                .map(c => ({
                    time: Math.floor(new Date(c.datetime).getTime() / 1000),
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close,
                }))
                .sort((a, b) => a.time - b.time);
            setCandles(formatted);
        } catch (_) {
            setCandles([]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchCandles(symbol, timeframe);
    }, [symbol, timeframe, fetchCandles]);

    const pct = quote?.percent_change;
    const isUp = pct != null && pct >= 0;
    const displayName = symbol ? symbol.replace('.NS', '') : '—';

    return (
        <div className="card chart-panel">
            <div className="chart-panel-header">
                <div className="chart-instrument">
                    <span className="chart-symbol mono">{displayName}</span>
                    <span className="chart-exchange">NSE</span>
                    {quote && (
                        <>
                            <span className="chart-price mono">₹{quote.price?.toLocaleString('en-IN')}</span>
                            <span className={`chart-change mono ${isUp ? 'up' : 'down'}`}>
                                {isUp ? '+' : ''}{quote.change?.toFixed(2)} ({isUp ? '+' : ''}{pct?.toFixed(2)}%)
                            </span>
                        </>
                    )}
                </div>
                <div className="chart-timeframes">
                    {TIMEFRAMES.map(tf => (
                        <button
                            key={tf.key}
                            className={`tf-btn ${timeframe === tf.key ? 'active' : ''}`}
                            onClick={() => setTimeframe(tf.key)}
                        >
                            {tf.key}
                        </button>
                    ))}
                </div>
            </div>

            <div className="chart-panel-body">
                {loading ? (
                    <div className="panel-loading" style={{ height: 320 }}>
                        <RefreshCw size={20} className="spin" /> Loading chart…
                    </div>
                ) : candles.length === 0 ? (
                    <div className="panel-empty" style={{ height: 320 }}>No candle data available for this timeframe.</div>
                ) : (
                    <CandlestickChart data={candles} height={320} timeframe={timeframe} />
                )}
            </div>
        </div>
    );
};

export default ChartPanel;
