import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
    LayoutDashboard, 
    History, 
    Briefcase, 
    TrendingUp, 
    Users, 
    Settings,
    Zap
} from 'lucide-react';

import { useAuth } from '../context/AuthContext';
import { LogOut } from 'lucide-react';

const Sidebar = () => {
    const { user, logout } = useAuth();
    const navItems = [
        { name: 'Dashboard', icon: <LayoutDashboard size={20} />, path: '/' },
        { name: 'Live Positions', icon: <Briefcase size={20} />, path: '/positions' },
        { name: 'Trade History', icon: <History size={20} />, path: '/history' },
        { name: 'AI Agents', icon: <Users size={20} />, path: '/agents' },
        { name: 'Market Heatmap', icon: <TrendingUp size={20} />, path: '/market' },
        { name: 'Settings', icon: <Settings size={20} />, path: '/settings' },
    ];

    return (
        <aside className="sidebar">
            <div className="sidebar-header">
                <Zap size={28} className="logo-icon" color="#3b82f6" fill="#3b82f6" />
                <h1 className="logo-text">Trade<span>OS</span></h1>
            </div>

            <nav className="sidebar-nav">
                {navItems.map((item) => (
                    <NavLink 
                        key={item.path} 
                        to={item.path}
                        className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                    >
                        {item.icon}
                        <span>{item.name}</span>
                    </NavLink>
                ))}
            </nav>

            <div className="sidebar-footer">
                {user && (
                    <div className="user-profile-badge">
                        <div className="user-info">
                            <span className="user-name">{user.username}</span>
                            <span className="user-role">{user.role}</span>
                        </div>
                        <button className="logout-btn" onClick={logout} title="Sign Out">
                            <LogOut size={16} />
                        </button>
                    </div>
                )}
                <div className="market-status">
                    <div className="status-dot online"></div>
                    <span>System Live</span>
                </div>
            </div>
        </aside>
    );
};

export default Sidebar;
