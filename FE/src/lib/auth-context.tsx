'use client';
/**
 * AuthContext — quản lý trạng thái đăng nhập toàn cục.
 * Wrap toàn bộ app bằng <AuthProvider> để dùng useAuth() ở bất cứ component nào.
 */
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react';
import * as api from './api';

interface AuthState {
  user: api.UserResponse | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<api.UserResponse | null>(null);
  const [loading, setLoading] = useState(true);

  // Khôi phục session khi reload trang
  useEffect(() => {
    const token = api.getToken();
    if (!token) { setLoading(false); return; }
    api.getMe()
      .then(setUser)
      .catch(() => api.removeToken())
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await api.login(email, password);
    const me = await api.getMe();
    setUser(me);
  }, []);

  const register = useCallback(async (email: string, password: string, fullName?: string) => {
    await api.register(email, password, fullName);
    await login(email, password);
  }, [login]);

  const logout = useCallback(() => {
    api.logout();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
