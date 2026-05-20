import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

const api = axios.create({
    baseURL: API_BASE,
    timeout: 15000,
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
    getCandles: (symbol) => api.get(`/market/candles/${symbol}`),
    getNews: (symbol) => api.get(`/market/news/${symbol}`),
    getMacroNews: () => api.get('/market/news/macro'),
    getHeatmap: () => api.get('/market/heatmap'),
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
    placeManualTrade: (data) => api.post('/broker/trade/manual', data),
};

export const performanceAPI = {
    getDaily: () => api.get('/broker/performance/daily'),
};

export const strategyAPI = {
    getTodayPreMarket: () => api.get('/scheduler/pre-market/today'),
    triggerPreMarket: () => api.post('/scheduler/pre-market'),
};

export default api;
