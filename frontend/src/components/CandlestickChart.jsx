import React, { useEffect, useRef } from 'react';
import { createChart, CrosshairMode, CandlestickSeries, createSeriesMarkers } from 'lightweight-charts';
import { nowChartTime } from '../utils/chartTime';

const CandlestickChart = ({
    data,
    markers = [],
    height = 500,
    liveTick = null,
    timeframe = '5d',
    entryPrice = null,
    targetPrice = null,
    stopLoss = null
}) => {
    const chartContainerRef = useRef(null);
    const chartRef = useRef(null);
    const seriesRef = useRef(null);
    const activeBarRef = useRef(null);
    const priceLinesRef = useRef([]);
    const hasFitContentRef = useRef(false);
    const markersPrimitiveRef = useRef(null);

    // Reset live bar tracker when historical timeframe data changes
    useEffect(() => {
        activeBarRef.current = null;
    }, [data]);

    // Create the chart+series ONCE (and on height change). A background candle refresh
    // must not land here — recreating the whole chart on every poll would wipe the
    // viewer's zoom/pan and cause a visible flicker every cycle.
    useEffect(() => {
        if (!chartContainerRef.current) return;

        const chart = createChart(chartContainerRef.current, {
            width: chartContainerRef.current.clientWidth,
            height: height,
            layout: {
                background: { color: '#101318' },
                textColor: '#A8B2C0',
                fontFamily: "'JetBrains Mono', monospace",
            },
            grid: {
                vertLines: { color: 'rgba(48, 57, 70, 0.35)' },
                horzLines: { color: 'rgba(48, 57, 70, 0.35)' },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
                vertLine: { color: 'rgba(255, 152, 0, 0.4)', labelVisible: true },
                horzLine: { color: 'rgba(255, 152, 0, 0.4)', labelVisible: true },
            },
            rightPriceScale: {
                borderColor: '#303946',
            },
            timeScale: {
                borderColor: '#303946',
                timeVisible: true,
            },
        });

        const candlestickSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#38D996',
            downColor: '#FF6673',
            borderDownColor: '#FF6673',
            borderUpColor: '#38D996',
            wickDownColor: '#FF6673',
            wickUpColor: '#38D996',
        });

        seriesRef.current = candlestickSeries;
        chartRef.current = chart;
        hasFitContentRef.current = false;

        const handleResize = () => {
            chart.applyOptions({ width: chartContainerRef.current.clientWidth });
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
            chartRef.current = null;
            seriesRef.current = null;
            priceLinesRef.current = [];
            markersPrimitiveRef.current = null;
        };
    }, [height]);

    // Update candle data in place on every prop change (including silent background
    // refreshes) instead of tearing down the chart. Only auto-fits the viewport the
    // first time data arrives for this chart instance, so later polls don't yank the
    // viewer's zoom/pan back to "fit all".
    useEffect(() => {
        if (!seriesRef.current) return;
        seriesRef.current.setData(data || []);
        if (!hasFitContentRef.current && data && data.length > 0) {
            chartRef.current?.timeScale().fitContent();
            hasFitContentRef.current = true;
        }
    }, [data]);

    // Markers change far less often than data — keep as its own effect.
    // lightweight-charts v5 moved markers off the series onto a separate primitive
    // (series.setMarkers was removed) — this was previously silently broken since it
    // only ever ran when markers.length > 0, and nothing in the app passes any yet.
    useEffect(() => {
        if (!seriesRef.current) return;
        if (!markersPrimitiveRef.current) {
            markersPrimitiveRef.current = createSeriesMarkers(seriesRef.current, markers || []);
        } else {
            markersPrimitiveRef.current.setMarkers(markers || []);
        }
    }, [markers]);

    // Entry/Target/Stop price lines: remove the previous set before drawing new ones,
    // since lightweight-charts has no "update" for an existing price line.
    useEffect(() => {
        if (!seriesRef.current) return;
        priceLinesRef.current.forEach(line => seriesRef.current.removePriceLine(line));
        priceLinesRef.current = [];

        if (entryPrice) {
            priceLinesRef.current.push(seriesRef.current.createPriceLine({
                price: Number(entryPrice),
                color: '#68B7FF',
                lineWidth: 2,
                lineStyle: 2,
                axisLabelVisible: true,
                title: 'Entry Price',
            }));
        }
        if (targetPrice) {
            priceLinesRef.current.push(seriesRef.current.createPriceLine({
                price: Number(targetPrice),
                color: '#38D996',
                lineWidth: 2,
                lineStyle: 2,
                axisLabelVisible: true,
                title: 'Target (TGT)',
            }));
        }
        if (stopLoss) {
            priceLinesRef.current.push(seriesRef.current.createPriceLine({
                price: Number(stopLoss),
                color: '#FF6673',
                lineWidth: 2,
                lineStyle: 2,
                axisLabelVisible: true,
                title: 'Stop Loss (SL)',
            }));
        }
    }, [entryPrice, targetPrice, stopLoss]);

    // Handle incoming continuous live price ticks (updating the active bar with high frequency)
    useEffect(() => {
        if (seriesRef.current && liveTick) {
            // The server sends `time` as a plain date STRING, not an epoch — dividing that by
            // 1000 previously produced NaN and silently dropped every live-tick update. What
            // actually matters here is which candle "bucket" is currently forming, so just use
            // the client clock (already IST-shifted the same way historical candles are).
            const timeVal = nowChartTime();

            // Map timeframe string to seconds
            let roundSeconds = 300; // default 5 minutes
            if (timeframe === '1m') roundSeconds = 3600; // 1 hour
            else if (timeframe === '1y' || timeframe === '5y') roundSeconds = 86400; // 1 day
            
            const alignedTime = Math.floor(timeVal / roundSeconds) * roundSeconds;
            const price = Number(liveTick.price);

            if (!activeBarRef.current || activeBarRef.current.time !== alignedTime) {
                // Initialize from the last candle in our data to avoid gaps
                const lastCandle = data && data.length > 0 ? data[data.length - 1] : null;
                if (lastCandle && lastCandle.time === alignedTime) {
                    activeBarRef.current = {
                        time: alignedTime,
                        open: Number(lastCandle.open),
                        high: Math.max(Number(lastCandle.high), price),
                        low: Math.min(Number(lastCandle.low), price),
                        close: price
                    };
                } else {
                    activeBarRef.current = {
                        time: alignedTime,
                        open: price,
                        high: price,
                        low: price,
                        close: price
                    };
                }
            } else {
                // Live sub-second updates to body and wicks
                activeBarRef.current.close = price;
                activeBarRef.current.high = Math.max(activeBarRef.current.high, price);
                activeBarRef.current.low = Math.min(activeBarRef.current.low, price);
            }
            
            seriesRef.current.update(activeBarRef.current);
        }
    }, [liveTick, timeframe, data]);

    return <div ref={chartContainerRef} style={{ position: 'relative', width: '100%' }} />;
};

export default CandlestickChart;
