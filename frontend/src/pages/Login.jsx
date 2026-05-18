import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import './Login.css';

const Login = () => {
    const { login, register } = useAuth();
    const [isLoginView, setIsLoginView] = useState(true);
    const [isLoading, setIsLoading] = useState(false);
    
    // Form fields
    const [username, setUsername] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);

        if (isLoginView) {
            await login(username, password);
        } else {
            if (password !== confirmPassword) {
                alert("Passwords do not match!");
                setIsLoading(false);
                return;
            }
            await register(username, email, password);
        }
        setIsLoading(false);
    };

    return (
        <div className="login-page-wrapper">
            <div className="animated-background-glow"></div>
            <div className="login-card-container">
                <div className="login-brand-header">
                    <span className="brand-logo-icon">🌌</span>
                    <h1>Trade<span>OS</span></h1>
                    <p className="brand-subtitle">Autonomous Multi-Agent AI Trading Terminal</p>
                </div>

                <div className="login-tabs" style={{ display: 'none' }}>
                    <button className="tab-btn active">Sign In</button>
                </div>

                <form className="login-form" onSubmit={handleSubmit}>
                    <div className="form-group">
                        <label htmlFor="username">Username</label>
                        <div className="input-wrapper">
                            <span className="input-icon">👤</span>
                            <input 
                                type="text" 
                                id="username" 
                                placeholder="Enter username" 
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                required 
                            />
                        </div>
                    </div>

                    <div className="form-group">
                        <label htmlFor="password">Password</label>
                        <div className="input-wrapper">
                            <span className="input-icon">🔒</span>
                            <input 
                                type="password" 
                                id="password" 
                                placeholder="••••••••" 
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                required 
                            />
                        </div>
                    </div>

                    <button 
                        type="submit" 
                        className="submit-action-btn" 
                        disabled={isLoading}
                    >
                        {isLoading ? (
                            <div className="form-spinner"></div>
                        ) : (
                            'Sign In to Terminal'
                        )}
                    </button>
                </form>

                <div className="login-card-footer" style={{ borderTop: 'none', paddingTop: '0' }}>
                    <p style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                        🔒 Secure TradeOS Algo Terminal
                    </p>
                </div>
            </div>
        </div>
    );
};

export default Login;
