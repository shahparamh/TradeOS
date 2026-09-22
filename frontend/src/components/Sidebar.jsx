import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
    LayoutDashboard,
    History,
    Briefcase,
    TrendingUp,
    Settings,
    Zap,
    Skull,
    ChevronsLeft,
    ChevronsRight,
} from 'lucide-react';

const Sidebar = () => {
    const [collapsed, setCollapsed] = useState(() => localStorage.getItem('tradeos_sidebar_collapsed') === 'true');

    const toggleCollapsed = () => {
        setCollapsed(prev => {
            const next = !prev;
            try { localStorage.setItem('tradeos_sidebar_collapsed', String(next)); } catch (_) { /* ignore */ }
            return next;
        });
    };

    const navItems = [
        { name: 'Dashboard', icon: <LayoutDashboard size={16} />, path: '/' },
        { name: 'Pre-Market Strategy', icon: <Zap size={16} />, path: '/pre-market' },
        { name: 'Live Positions', icon: <Briefcase size={16} />, path: '/positions' },
        { name: 'Trade History', icon: <History size={16} />, path: '/history' },
        // 'AI Agents' hidden for now — page and routes still exist, just not linked in nav.
        { name: 'Survival Arena', icon: <Skull size={16} />, path: '/arena' },
        { name: 'Market Heatmap', icon: <TrendingUp size={16} />, path: '/market' },
        { name: 'Settings', icon: <Settings size={16} />, path: '/settings' },
    ];

    return (
        <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
            <nav className="sidebar-nav">
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                        title={collapsed ? item.name : undefined}
                    >
                        {item.icon}
                        <span>{item.name}</span>
                    </NavLink>
                ))}
            </nav>

            <div className="sidebar-footer">
                <button
                    className="sidebar-collapse-btn"
                    onClick={toggleCollapsed}
                    title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                    aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
                >
                    {collapsed ? <ChevronsRight size={14} /> : <ChevronsLeft size={14} />}
                    {!collapsed && <span>Collapse</span>}
                </button>
                <div className="market-status">
                    <div className="status-dot online"></div>
                    {!collapsed && <span>System Live</span>}
                </div>
            </div>
        </aside>
    );
};

export default Sidebar;
