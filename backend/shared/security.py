import os
import jwt
from typing import List
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.shared.exceptions import AuthenticationError, AuthorizationError

from functools import lru_cache

security_scheme = HTTPBearer()

@lru_cache
def get_jwks_client() -> jwt.PyJWKClient:
    jwks_url = os.getenv("JWKS_URL")
    if not jwks_url:
        raise RuntimeError("JWKS_URL must be configured when ENABLE_AUTH is true.")
    return jwt.PyJWKClient(jwks_url)

def verify_jwt(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    """
    Validates a JWT against a remote JWKS URL. 
    Production deployments must set the JWKS_URL and JWT_AUDIENCE environment variables.
    """
    token = credentials.credentials

    # Configuration errors must surface as server errors (RuntimeError -> 500),
    # not as client-facing AuthenticationError (401). Both the audience and the
    # JWKS client are validated *before* the token-verification try/except so a
    # misconfigured deployment is never mistaken for a bad token. (get_jwks_client
    # itself raises RuntimeError when JWKS_URL is unset.)
    audience = os.getenv("JWT_AUDIENCE")
    if not audience:
        raise RuntimeError("JWT_AUDIENCE must be configured when ENABLE_AUTH is true.")

    jwks_client = get_jwks_client()

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=audience
        )
        return payload
    except jwt.PyJWKClientError as e:
        raise AuthenticationError(f"Unable to fetch signing keys: {str(e)}")
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise AuthenticationError(f"Invalid token: {str(e)}")
    except Exception as e:
        raise AuthenticationError(f"Authentication failed: {str(e)}")


def require_role(*allowed_roles: str):
    """Dependency factory that gates a route by role claim in the JWT.

    Usage::

        @router.post("/admin/reset", dependencies=[Depends(require_role("admin"))])
        async def reset(): ...

    The role claim is read from the ``role`` key in the JWT payload (set by
    most identity providers).  If the claim is missing or does not match any
    of *allowed_roles*, a 403 is returned.
    """
    def _check(claims: dict = Depends(verify_jwt)):
        user_role = claims.get("role") or claims.get("roles") or claims.get("user_role", "viewer")
        # Support both single-string and list-of-strings role claims.
        if isinstance(user_role, list):
            if not any(r in allowed_roles for r in user_role):
                raise AuthorizationError(f"Required role(s): {', '.join(allowed_roles)}")
        else:
            if user_role not in allowed_roles:
                raise AuthorizationError(f"Required role(s): {', '.join(allowed_roles)}")
        return claims
    return Depends(_check)


def get_current_user(claims: dict = Depends(verify_jwt)) -> dict:
    """Dependency that extracts the authenticated user's identity from JWT claims.
    
    Returns a dict with at minimum 'sub' (subject) and 'role' keys.
    """
    return {
        "sub": claims.get("sub", "unknown"),
        "role": claims.get("role") or claims.get("roles") or claims.get("user_role", "viewer"),
        "email": claims.get("email"),
    }

