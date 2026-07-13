'use client';

import { createContext, useContext, useState, useCallback, useEffect, useRef, type ReactNode } from 'react';
import type { AuthState, Role } from './types';
import { devIssueToken, DEMO_USERS } from './mock-data';
import { userFromClaims, isExpired } from './jwt';
import { config } from './config';

type LoginResult = { ok: true } | { ok: false; error: string };

interface AuthContextType extends AuthState {
  login: (username: string, password: string) => Promise<LoginResult>;
  logout: () => void;
  hasPermission: (permission: string) => boolean;
  isLoading: boolean;
  /** 'real' when an identity provider is configured, otherwise 'dev'. */
  authMode: 'real' | 'dev';
  /** Whether the built-in dev accounts can be used to sign in. */
  devLoginAvailable: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

const ROLE_PERMISSIONS: Record<Role, string[]> = {
  technician: ['query', 'graph:read', 'entity:read', 'feedback:create'],
  engineer: ['query', 'graph:read', 'graph:write', 'entity:read', 'entity:write', 'feedback:create', 'feedback:confirm', 'agents:diagnose', 'agents:risk', 'documents:upload'],
  compliance_officer: ['query', 'graph:read', 'entity:read', 'compliance:read', 'compliance:write', 'agents:comply', 'documents:upload'],
  admin: ['query', 'graph:read', 'graph:write', 'entity:read', 'entity:write', 'feedback:create', 'feedback:confirm', 'agents:diagnose', 'agents:risk', 'agents:comply', 'compliance:read', 'compliance:write', 'documents:upload', 'admin:users', 'admin:system'],
};

const STORAGE_KEY = 'seekr_auth';

interface StoredAuth extends AuthState {
  expiresAt: number | null;
}

const EMPTY: StoredAuth = { user: null, token: null, isAuthenticated: false, expiresAt: null };

function loadStored(): StoredAuth {
  if (typeof window === 'undefined') return EMPTY;
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return EMPTY;
    const parsed = JSON.parse(saved) as StoredAuth;
    if (parsed.isAuthenticated && parsed.user && parsed.token && !isExpired(parsed.expiresAt)) {
      return parsed;
    }
  } catch { }
  localStorage.removeItem(STORAGE_KEY);
  return EMPTY;
}

/** Session built from a verified/issued JWT — the single source of identity. */
function sessionFromToken(token: string): StoredAuth | null {
  const decoded = userFromClaims(token);
  if (!decoded) return null;
  return { user: decoded.user, token, isAuthenticated: true, expiresAt: decoded.expiresAt };
}

async function requestRealToken(username: string, password: string): Promise<string> {
  const res = await fetch(config.authUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, grant_type: 'password' }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail || detail?.error_description || `Sign-in failed (${res.status})`);
  }
  const data = await res.json();
  const token = data.access_token || data.token || data.id_token;
  if (!token) throw new Error('Identity provider returned no access token.');
  return token as string;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<StoredAuth>(EMPTY);
  const [isLoading, setIsLoading] = useState(true);
  const expiryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const authMode: 'real' | 'dev' = config.authUrl ? 'real' : 'dev';
  const devLoginAvailable = config.allowDevLogin;

  const applySession = useCallback((session: StoredAuth) => {
    setState(session);
    if (session.isAuthenticated) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const logout = useCallback(() => {
    if (expiryTimer.current) clearTimeout(expiryTimer.current);
    applySession(EMPTY);
  }, [applySession]);

  // Hydrate from storage on mount and schedule auto-logout at token expiry.
  useEffect(() => {
    const restored = loadStored();
    setState(restored);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    if (expiryTimer.current) clearTimeout(expiryTimer.current);
    if (state.isAuthenticated && state.expiresAt) {
      const ms = state.expiresAt - Date.now();
      if (ms <= 0) { logout(); return; }
      expiryTimer.current = setTimeout(logout, ms);
    }
    return () => { if (expiryTimer.current) clearTimeout(expiryTimer.current); };
  }, [state.isAuthenticated, state.expiresAt, logout]);

  const login = useCallback(async (username: string, password: string): Promise<LoginResult> => {
    try {
      let token: string;
      if (config.authUrl) {
        token = await requestRealToken(username, password);
      } else if (config.allowDevLogin) {
        const dev = devIssueToken(username, password);
        if (!dev) return { ok: false, error: 'Invalid credentials' };
        token = dev;
      } else {
        return { ok: false, error: 'No identity provider configured. Set NEXT_PUBLIC_AUTH_URL.' };
      }

      const session = sessionFromToken(token);
      if (!session) return { ok: false, error: 'Received a malformed token.' };
      applySession(session);
      return { ok: true };
    } catch (err) {
      return { ok: false, error: err instanceof Error ? err.message : 'Sign-in failed' };
    }
  }, [applySession]);

  const hasPermission = useCallback((permission: string): boolean => {
    if (!state.user) return false;
    return ROLE_PERMISSIONS[state.user.role]?.includes(permission) ?? false;
  }, [state.user]);

  return (
    <AuthContext.Provider
      value={{
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
        login,
        logout,
        hasPermission,
        isLoading,
        authMode,
        devLoginAvailable,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

export { DEMO_USERS };
