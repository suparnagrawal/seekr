import type { User, LoginResponse } from './types';

export const DEMO_USERS: Record<string, { password: string; user: User }> = {
  technician: {
    password: 'tech123',
    user: { id: 'u-1', username: 'technician', role: 'technician', display_name: 'Alex Rivera' },
  },
  engineer: {
    password: 'eng123',
    user: { id: 'u-2', username: 'engineer', role: 'engineer', display_name: 'Jordan Chen' },
  },
  compliance_officer: {
    password: 'comp123',
    user: { id: 'u-3', username: 'compliance_officer', role: 'compliance_officer', display_name: 'Morgan Hayes' },
  },
  admin: {
    password: 'admin123',
    user: { id: 'u-4', username: 'admin', role: 'admin', display_name: 'Casey Brooks' },
  },
};

export function mockLogin(username: string, password: string): LoginResponse | null {
  const entry = DEMO_USERS[username];
  if (!entry || entry.password !== password) return null;
  return {
    access_token: `mock-jwt-${username}-${Date.now()}`,
    token_type: 'bearer',
    user: entry.user,
  };
}
