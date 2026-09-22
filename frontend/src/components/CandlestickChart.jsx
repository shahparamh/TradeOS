import React, { useEffect, useRef } from 'react';
import { createChart, CrosshairMode, CandlestickSeries } from 'lightweight-charts';

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

    // Reset live bar tracker when historical timeframe data changes
    useEffect(() => {
        activeBarRef.current = null;
    }, [data]);

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

        candlestickSeries.setData(data);
        seriesRef.current = candlestickSeries;

        // Draw Entry, Target, and Stop Loss Price Lines
        if (entryPrice) {
            candlestickSeries.createPriceLine({
                price: Number(entryPrice),
                color: '#68B7FF', // Blue for Entry
                lineWidth: 2,
                lineStyle: 2, // Dashed
                axisLabelVisible: true,
                title: 'Entry Price',
            });
        }

        if (targetPrice) {
            candlestickSeries.createPriceLine({
                price: Number(targetPrice),
                color: '#38D996', // Green for Target
                lineWidth: 2,
                lineStyle: 2, // Dashed
                axisLabelVisible: true,
                title: 'Target (TGT)',
            });
        }

        if (stopLoss) {
            candlestickSeries.createPriceLine({
                price: Number(stopLoss),
                color: '#FF6673', // Red for Stop Loss
                lineWidth: 2,
                lineStyle: 2, // Dashed
                axisLabelVisible: true,
                title: 'Stop Loss (SL)',
            });
        }

        if (markers.length > 0) {
            candlestickSeries.setMarkers(markers);
        }

        chart.timeScale().fitContent();
        chartRef.current = chart;

        const handleResize = () => {
            chart.applyOptions({ width: chartContainerRef.current.clientWidth });
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, [data, markers, height, entryPrice, targetPrice, stopLoss]);

    // Handle incoming continuous live price ticks (updating the active bar with high frequency)
    useEffect(() => {
        if (seriesRef.current && liveTick) {
            const timeVal = liveTick.time 
                ? (String(liveTick.time).length > 10 ? Math.floor(liveTick.time / 1000) : liveTick.time)
                : Math.floor(Date.now() / 1000);
            
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
