/**
 * Centralized runtime configuration for the SEEKR frontend.
 *
 * Every externally-configurable value is sourced from an environment variable
 * (see `.env.example`). No host, URL, port, or environment-specific literal is
 * hardcoded anywhere in application source — change behaviour by editing `.env`,
 * never by editing code.
 *
 * Note: Next.js inlines `NEXT_PUBLIC_*` variables at build time, so these are
 * resolved when the bundle is built, not at request time in the browser.
 */

function requireEnv(name: string, value: string | undefined): string {
  if (!value || value.trim() === '') {
    throw new Error(
      `Missing required environment variable ${name}. ` +
      `Copy frontend/.env.example to frontend/.env and set ${name} before building.`,
    );
  }
  return value.trim();
}

function optionalEnv(value: string | undefined, fallback: string): string {
  return value && value.trim() !== '' ? value.trim() : fallback;
}

/** Strip any trailing slashes so we can safely concatenate path segments. */
function stripTrailingSlash(url: string): string {
  return url.replace(/\/+$/, '');
}

/** Ensure a path prefix starts with exactly one leading slash. */
function normalizePrefix(prefix: string): string {
  const trimmed = prefix.trim().replace(/\/+$/, '');
  return trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
}

const apiUrl = stripTrailingSlash(requireEnv('NEXT_PUBLIC_API_URL', process.env.NEXT_PUBLIC_API_URL));
const apiPrefix = normalizePrefix(optionalEnv(process.env.NEXT_PUBLIC_API_PREFIX, '/api/v1'));

export const config = {
  /** Base URL of the SEEKR backend, e.g. https://api.seekr.example.com */
  apiUrl,
  /** Versioned API path prefix, must match the backend's API_V1_PREFIX. */
  apiPrefix,
  /** Fully-qualified versioned API root: `${apiUrl}${apiPrefix}`. */
  apiV1: `${apiUrl}${apiPrefix}`,
  /** Product name shown in the UI shell. */
  appName: optionalEnv(process.env.NEXT_PUBLIC_APP_NAME, 'SEEKR'),
  /** Entity the knowledge-graph landing view centres on by default. */
  defaultEntityTag: optionalEnv(process.env.NEXT_PUBLIC_DEFAULT_ENTITY, ''),
  /** Default knowledge-graph traversal depth. */
  defaultGraphDepth: Number(optionalEnv(process.env.NEXT_PUBLIC_DEFAULT_GRAPH_DEPTH, '2')),
  /** Maximum upload size in megabytes (should mirror the backend limit). */
  maxUploadMb: Number(optionalEnv(process.env.NEXT_PUBLIC_MAX_UPLOAD_MB, '50')),
  /** Timeout (ms) applied to non-streaming API requests. */
  requestTimeoutMs: Number(optionalEnv(process.env.NEXT_PUBLIC_REQUEST_TIMEOUT_MS, '30000')),
  /**
   * Optional token-issuing endpoint (an identity provider or a backend auth
   * route) that exchanges credentials for a real, JWKS-verifiable JWT. When set,
   * the login flow POSTs credentials here and attaches the returned token as a
   * Bearer to every API call — the JWT the backend's `verify_jwt` expects.
   */
  authUrl: optionalEnv(process.env.NEXT_PUBLIC_AUTH_URL, ''),
  /**
   * Whether the built-in development login (unsigned, role-scoped dev tokens) is
   * permitted. Defaults to enabled only when no real `authUrl` is configured, so
   * production builds that point at a real IdP never expose the dev path.
   */
  allowDevLogin:
    optionalEnv(process.env.NEXT_PUBLIC_ALLOW_DEV_LOGIN, '') !== ''
      ? optionalEnv(process.env.NEXT_PUBLIC_ALLOW_DEV_LOGIN, 'false') === 'true'
      : optionalEnv(process.env.NEXT_PUBLIC_AUTH_URL, '') === '',
} as const;

export const API_BASE = config.apiUrl;
export const API_V1 = config.apiV1;
