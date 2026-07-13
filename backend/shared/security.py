import os
import jwt
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from backend.shared.exceptions import AuthenticationError

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
