import type { User, Role } from './types';

/**
 * Development-only identity issuance.
 *
 * These are NOT production credentials. When no real identity provider is
 * configured (`NEXT_PUBLIC_AUTH_URL`), the login flow may fall back to issuing
 * an *unsigned* (`alg: "none"`) dev JWT so the rest of the app — token storage,
 * claim decoding, Bearer attachment, expiry handling — exercises the exact same
 * code path a real token would. A real backend running with `ENABLE_AUTH=true`
 * and a JWKS endpoint will correctly REJECT these tokens; they only work against
 * a local backend with auth disabled, which is the intended dev posture.
 */

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

function base64url(obj: unknown): string {
  const json = JSON.stringify(obj);
  const b64 = btoa(unescape(encodeURIComponent(json)));
  return b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** Mint an unsigned, claim-bearing dev JWT (header.payload. — empty signature). */
function issueDevToken(user: User): string {
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: 'none', typ: 'JWT' };
  const payload = {
    sub: user.id,
    username: user.username,
    name: user.display_name,
    role: user.role as Role,
    iss: 'seekr-dev',
    iat: now,
    exp: now + 60 * 60 * 8, // 8h dev session
    dev: true,
  };
  return `${base64url(header)}.${base64url(payload)}.`;
}

/** Returns a dev-issued JWT string on valid credentials, else null. */
export function devIssueToken(username: string, password: string): string | null {
  const entry = DEMO_USERS[username];
  if (!entry || entry.password !== password) return null;
  return issueDevToken(entry.user);
}
