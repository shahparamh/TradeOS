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

                <div className="login-tabs">
                    <button 
                        className={`tab-btn ${isLoginView ? 'active' : ''}`}
                        onClick={() => { setIsLoginView(true); setUsername(''); setPassword(''); }}
                    >
                        Sign In
                    </button>
                    <button 
                        className={`tab-btn ${!isLoginView ? 'active' : ''}`}
                        onClick={() => { setIsLoginView(false); setUsername(''); setEmail(''); setPassword(''); setConfirmPassword(''); }}
                    >
                        Register
                    </button>
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

                    {!isLoginView && (
                        <div className="form-group">
                            <label htmlFor="email">Email Address</label>
                            <div className="input-wrapper">
                                <span className="input-icon">✉️</span>
                                <input 
                                    type="email" 
                                    id="email" 
                                    placeholder="Enter your email" 
                                    value={email}
                                    onChange={(e) => setEmail(e.target.value)}
                                    required 
                                />
                            </div>
                        </div>
                    )}

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

                    {!isLoginView && (
                        <div className="form-group">
                            <label htmlFor="confirmPassword">Confirm Password</label>
                            <div className="input-wrapper">
                                <span className="input-icon">🛡️</span>
                                <input 
                                    type="password" 
                                    id="confirmPassword" 
                                    placeholder="••••••••" 
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    required 
                                />
                            </div>
                        </div>
                    )}

                    <button 
                        type="submit" 
                        className="submit-action-btn" 
                        disabled={isLoading}
                    >
                        {isLoading ? (
                            <div className="form-spinner"></div>
                        ) : (
                            isLoginView ? 'Sign In to Terminal' : 'Create TradeOS Account'
                        )}
                    </button>
                </form>

                <div className="login-card-footer">
                    <p>
                        {isLoginView 
                            ? "Don't have an account? " 
                            : "Already have a TradeOS account? "
                        }
                        <span 
                            className="toggle-view-link"
                            onClick={() => setIsLoginView(!isLoginView)}
                        >
                            {isLoginView ? 'Register here' : 'Sign in here'}
                        </span>
                    </p>
                    {isLoginView && (
                        <p className="demo-credentials-hint">
                            💡 Try signing in with <strong>admin</strong> and password <strong>adminpassword</strong>
                        </p>
                    )}
                </div>
            </div>
        </div>
    );
};

export default Login;
