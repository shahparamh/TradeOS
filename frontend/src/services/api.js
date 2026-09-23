import axios from 'axios';

// Relative by default: works unmodified both in local dev (Vite proxies /api to the
// backend, see vite.config.js) and in production (FastAPI serves the built frontend and
// the API from the same origin — see the static-file mount at the bottom of backend/main.py).
// VITE_API_URL stays available as an override for a split-service deployment.
const API_BASE = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
    baseURL: API_BASE,
    timeout: 30000,
});

// Interceptor to inject JWT token automatically
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('tradeos_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});

export const authAPI = {
    login: (username, password) => {
        const params = new URLSearchParams();
        params.append('username', username);
        params.append('password', password);
        return api.post('/auth/login', params, {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        });
    },
    register: (username, email, password) => api.post('/auth/register', { username, email, password }),
    getMe: () => api.get('/auth/me'),
};

export const settingsAPI = {
    getRules: () => api.get('/settings/rules'),
    updateRules: (rules) => api.put('/settings/rules', { rules }),
};

export const marketAPI = {
    getIndices: () => api.get('/market/indices'),
    getPrice: (symbol) => api.get(`/market/price/${symbol}`),
    getPrices: (symbols) => api.get(`/market/prices?symbols=${symbols.join(',')}`),
    getCandles: (symbol) => api.get(`/market/candles/${symbol}`),
    getNews: (symbol) => api.get(`/market/news/${symbol}`),
    getMacroNews: () => api.get('/market/news/macro'),
    getHeatmap: () => api.get('/market/heatmap'),
    getWatchlist: () => api.get('/market/watchlist'),
};

export const agentAPI = {
    getAll: () => api.get('/agents/'),
    getById: (id) => api.get(`/agents/${id}`),
    getAgentTrades: (id) => api.get(`/agents/${id}/trades`),
    triggerScan: (agentId, symbol) => api.post(`/agents/${agentId}/scan/${symbol}`),
    toggleStatus: (id) => api.post(`/agents/${id}/toggle`),
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

export const strategyAPI = {
    getTodayPreMarket: () => api.get('/scheduler/pre-market/today'),
    triggerPreMarket: () => api.post('/scheduler/pre-market'),
};

export const arenaAPI = {
    getAgents: () => api.get('/arena/agents'),
    getAgentDetail: (id) => api.get(`/arena/agents/${id}`),
    createAgent: (data) => api.post('/arena/agents', data),
    getStatus: () => api.get('/arena/status'),
    getMarket: () => api.get('/arena/market'),
    emergencyStop: () => api.post('/arena/emergency-stop'),
    resume: () => api.post('/arena/resume'),
    triggerCycle: () => api.post('/arena/cycle-trigger'),
};

export default api;
