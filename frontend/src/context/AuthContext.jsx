import React, { createContext, useState, useEffect, useContext } from 'react';
import { authAPI } from '../services/api';
import toast from 'react-hot-toast';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [user, setUser] = useState(null);
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const verifyUser = async () => {
            const token = localStorage.getItem('tradeos_token');
            if (!token) {
                setIsLoading(false);
                return;
            }

            try {
                const response = await authAPI.getMe();
                setUser(response.data);
                setIsAuthenticated(true);
            } catch (error) {
                console.error("Token verification failed", error);
                localStorage.removeItem('tradeos_token');
                setUser(null);
                setIsAuthenticated(false);
            } finally {
                setIsLoading(false);
            }
        };

        verifyUser();
    }, []);

    const login = async (username, password) => {
        setIsLoading(true);
        try {
            const response = await authAPI.login(username, password);
            const { access_token } = response.data;
            localStorage.setItem('tradeos_token', access_token);
            
            // Get user details
            const userProfile = await authAPI.getMe();
            setUser(userProfile.data);
            setIsAuthenticated(true);
            toast.success(`Welcome back, ${userProfile.data.username}!`);
            return true;
        } catch (error) {
            const message = error.response?.data?.detail || "Invalid credentials. Please try again.";
            toast.error(message);
            return false;
        } finally {
            setIsLoading(false);
        }
    };

    const register = async (username, email, password) => {
        setIsLoading(true);
        try {
            await authAPI.register(username, email, password);
            toast.success("Account created successfully! Logging you in...");
            // Auto login after registration
            return await login(username, password);
        } catch (error) {
            const message = error.response?.data?.detail || "Registration failed. Username or email may already be in use.";
            toast.error(message);
            return false;
        } finally {
            setIsLoading(false);
        }
    };

    const logout = () => {
        localStorage.removeItem('tradeos_token');
        setUser(null);
        setIsAuthenticated(false);
        toast.success("Logged out successfully.");
    };

    return (
        <AuthContext.Provider value={{ user, isAuthenticated, isLoading, login, register, logout }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error("useAuth must be used within an AuthProvider");
    }
    return context;
};
