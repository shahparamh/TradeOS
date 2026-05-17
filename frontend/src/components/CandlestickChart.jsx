import React, { useEffect, useRef } from 'react';
import { createChart, CrosshairMode, CandlestickSeries } from 'lightweight-charts';

const CandlestickChart = ({ data, markers = [], height = 500 }) => {
    const chartContainerRef = useRef(null);
    const chartRef = useRef(null);

    useEffect(() => {
        if (!chartContainerRef.current) return;

        const chart = createChart(chartContainerRef.current, {
            width: chartContainerRef.current.clientWidth,
            height: height,
            layout: {
                background: { color: '#0a0e17' },
                textColor: '#94a3b8',
            },
            grid: {
                vertLines: { color: 'rgba(30, 41, 59, 0.2)' },
                horzLines: { color: 'rgba(30, 41, 59, 0.2)' },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
                vertLine: { color: 'rgba(59, 130, 246, 0.4)', labelVisible: true },
                horzLine: { color: 'rgba(59, 130, 246, 0.4)', labelVisible: true },
            },
            rightPriceScale: {
                borderColor: '#1e293b',
            },
            timeScale: {
                borderColor: '#1e293b',
                timeVisible: true,
            },
        });

        const candlestickSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#22c55e',
            downColor: '#ef4444',
            borderDownColor: '#ef4444',
            borderUpColor: '#22c55e',
            wickDownColor: '#ef4444',
            wickUpColor: '#22c55e',
        });

        candlestickSeries.setData(data);

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
    }, [data, markers, height]);

    return <div ref={chartContainerRef} style={{ position: 'relative', width: '100%' }} />;
};

export default CandlestickChart;
