import React, { Suspense, lazy } from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import { AuthProvider, useAuth } from './context/AuthContext';
import './App.css';

// Everything but Login/Dashboard is lazy-loaded per route: keeps the initial JS bundle
// (parsed before the terminal can render anything) limited to the screens every session
// hits first, instead of shipping every page's code up front.
const PreMarket = lazy(() => import('./pages/PreMarket'));
const Positions = lazy(() => import('./pages/Positions'));
const History = lazy(() => import('./pages/History'));
const Agents = lazy(() => import('./pages/Agents'));
const Market = lazy(() => import('./pages/Market'));
const Settings = lazy(() => import('./pages/Settings'));
const AgentDetail = lazy(() => import('./pages/AgentDetail'));
const Arena = lazy(() => import('./pages/Arena'));
const ArenaAgentDetail = lazy(() => import('./pages/ArenaAgentDetail'));

const RouteFallback = () => (
  <div className="loading-screen">
    <div className="spin">⚡</div>
    <span>LOADING...</span>
  </div>
);

function AppContent() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="loading-screen">
        <div className="spin">⚡</div>
        <span>INITIALIZING TERMINAL...</span>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Login />;
  }

  return (
    <div className="app-container">
      <TopBar />
      <Sidebar />
      <main className="main-content">
        <Suspense fallback={<RouteFallback />}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/pre-market" element={<PreMarket />} />
            <Route path="/positions" element={<Positions />} />
            <Route path="/history" element={<History />} />
            <Route path="/agents" element={<Agents />} />
            <Route path="/agent/:agentId" element={<AgentDetail />} />
            <Route path="/arena" element={<Arena />} />
            <Route path="/arena/:agentId" element={<ArenaAgentDetail />} />
            <Route path="/market" element={<Market />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}

function App() {
  return (
    <Router>
      <AuthProvider>
        <AppContent />
        <Toaster
          position="bottom-right"
          toastOptions={{
            style: {
              background: '#171C23',
              color: '#E6EAF0',
              border: '1px solid #303946',
              borderRadius: '3px',
              fontSize: '13px',
            },
          }}
        />
      </AuthProvider>
    </Router>
  );
}

export default App;
