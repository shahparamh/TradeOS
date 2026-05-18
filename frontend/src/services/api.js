import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
    baseURL: API_BASE,
    timeout: 15000,
});

export const marketAPI = {
    getIndices: () => api.get('/market/indices'),
    getPrice: (symbol) => api.get(`/market/price/${symbol}`),
    getCandles: (symbol) => api.get(`/market/candles/${symbol}`),
    getNews: (symbol) => api.get(`/market/news/${symbol}`),
    getHeatmap: () => api.get('/market/heatmap'),
};

export const agentAPI = {
    getAll: () => api.get('/agents/'),
    getById: (id) => api.get(`/agents/${id}`),
    getAgentTrades: (id) => api.get(`/agents/${id}/trades`),
    triggerScan: (agentId, symbol) => api.post(`/agents/${agentId}/scan/${symbol}`),
};

export const brokerAPI = {
    getTrades: () => api.get('/broker/trades'),
    getPositions: () => api.get('/broker/positions'),
    getLeaderboard: () => api.get('/broker/leaderboard'),
    closePosition: (id) => api.post(`/broker/positions/${id}/close`),
    getAgentStatus: (id) => api.get(`/broker/agents/${id}/status`),
    getDaily: () => api.get('/broker/performance/daily'),
};

export const performanceAPI = {
    getDaily: () => api.get('/broker/performance/daily'),
};

export default api;
