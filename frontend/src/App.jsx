import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import Positions from './pages/Positions';
import History from './pages/History';
import Agents from './pages/Agents';
import Market from './pages/Market';
import Settings from './pages/Settings';
import AgentDetail from './pages/AgentDetail';
import './App.css';

function App() {
  return (
    <Router>
      <div className="app-container">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/positions" element={<Positions />} />
            <Route path="/history" element={<History />} />
            <Route path="/agents" element={<Agents />} />
            <Route path="/agent/:agentId" element={<AgentDetail />} />
            <Route path="/market" element={<Market />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
        <Toaster 
          position="bottom-right"
          toastOptions={{
            style: {
              background: '#1a2332',
              color: '#e2e8f0',
              border: '1px solid #1e293b',
            },
          }}
        />
      </div>
    </Router>
  );
}

export default App;
