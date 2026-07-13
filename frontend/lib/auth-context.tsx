'use client';

import { createContext, useContext, useState, useCallback, type ReactNode } from 'react';
import type { AuthState, User, Role } from './types';
import { mockLogin } from './mock-data';

interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  hasPermission: (permission: string) => boolean;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

const ROLE_PERMISSIONS: Record<Role, string[]> = {
  technician: ['query', 'graph:read', 'entity:read', 'feedback:create'],
  engineer: ['query', 'graph:read', 'graph:write', 'entity:read', 'entity:write', 'feedback:create', 'feedback:confirm', 'agents:diagnose', 'agents:risk', 'documents:upload'],
  compliance_officer: ['query', 'graph:read', 'entity:read', 'compliance:read', 'compliance:write', 'agents:comply', 'documents:upload'],
  admin: ['query', 'graph:read', 'graph:write', 'entity:read', 'entity:write', 'feedback:create', 'feedback:confirm', 'agents:diagnose', 'agents:risk', 'agents:comply', 'compliance:read', 'compliance:write', 'documents:upload', 'admin:users', 'admin:system'],
};

function getInitialState(): AuthState {
  if (typeof window === 'undefined') {
    return { user: null, token: null, isAuthenticated: false };
  }
  try {
    const saved = localStorage.getItem('seekr_auth');
    if (saved) {
      const parsed = JSON.parse(saved);
      if (parsed.isAuthenticated && parsed.user && parsed.token) {
        return parsed;
      }
    }
  } catch {}
  return { user: null, token: null, isAuthenticated: false };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(getInitialState);

  const login = useCallback(async (username: string, password: string): Promise<boolean> => {
    const response = mockLogin(username, password);
    if (!response) return false;

    const newState: AuthState = {
      user: response.user,
      token: response.access_token,
      isAuthenticated: true,
    };
    setState(newState);
    localStorage.setItem('seekr_auth', JSON.stringify(newState));
    return true;
  }, []);

  const logout = useCallback(() => {
    setState({ user: null, token: null, isAuthenticated: false });
    localStorage.removeItem('seekr_auth');
  }, []);

  const hasPermission = useCallback((permission: string): boolean => {
    if (!state.user) return false;
    return ROLE_PERMISSIONS[state.user.role]?.includes(permission) ?? false;
  }, [state.user]);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, hasPermission, isLoading: false }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
