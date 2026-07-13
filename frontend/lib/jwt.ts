import type { Role, User } from './types';

/** Base64URL-decode a JWT segment into a UTF-8 JSON object. */
export function decodeJwtClaims(token: string): Record<string, unknown> | null {
  try {
    const payload = token.split('.')[1];
    if (!payload) return null;
    const b64 = payload.replace(/-/g, '+').replace(/_/g, '/').padEnd(payload.length + ((4 - (payload.length % 4)) % 4), '=');
    const json = decodeURIComponent(
      atob(b64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join(''),
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

const VALID_ROLES: Role[] = ['technician', 'engineer', 'compliance_officer', 'admin'];

function coerceRole(claims: Record<string, unknown>): Role {
  const candidates: unknown[] = [
    claims.role,
    Array.isArray(claims.roles) ? claims.roles[0] : undefined,
    claims['seekr_role'],
    Array.isArray(claims['https://seekr/roles']) ? (claims['https://seekr/roles'] as unknown[])[0] : undefined,
  ];
  for (const c of candidates) {
    if (typeof c === 'string' && (VALID_ROLES as string[]).includes(c)) return c as Role;
  }
  return 'technician';
}

/** Build the app's `User` from verified JWT claims. */
export function userFromClaims(token: string): { user: User; expiresAt: number | null } | null {
  const claims = decodeJwtClaims(token);
  if (!claims) return null;

  const sub = (claims.sub as string) || (claims.username as string) || 'user';
  const user: User = {
    id: sub,
    username: (claims.username as string) || (claims.preferred_username as string) || sub,
    role: coerceRole(claims),
    display_name:
      (claims.name as string) || (claims.display_name as string) || (claims.username as string) || sub,
  };
  const expiresAt = typeof claims.exp === 'number' ? claims.exp * 1000 : null;
  return { user, expiresAt };
}

export function isExpired(expiresAt: number | null): boolean {
  return expiresAt !== null && Date.now() >= expiresAt;
}
