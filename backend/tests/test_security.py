"""Unit tests for shared/security.py verify_jwt.

The single most security-critical module in the backend previously had no
dedicated coverage. These tests exercise the branches that matter: missing
configuration, expired / malformed / wrong-audience / wrong-signature tokens,
and the happy path — all with the JWKS client and jwt.decode mocked so no
network or real keys are required.
"""

import jwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials

import backend.shared.security as security
from backend.shared.security import verify_jwt, get_jwks_client
from backend.shared.exceptions import AuthenticationError


def _creds(token: str = "dummy.token.value") -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture(autouse=True)
def _clear_jwks_cache():
    # get_jwks_client is lru_cache'd; reset between tests so env changes take effect.
    get_jwks_client.cache_clear()
    yield
    get_jwks_client.cache_clear()


@pytest.fixture
def configured_env(monkeypatch):
    monkeypatch.setenv("JWKS_URL", "https://issuer.example/.well-known/jwks.json")
    monkeypatch.setenv("JWT_AUDIENCE", "seekr-api")


class _FakeSigningKey:
    key = "fake-public-key"


class _FakeJWKSClient:
    def get_signing_key_from_jwt(self, token):
        return _FakeSigningKey()


def test_missing_audience_raises_runtime_error(monkeypatch):
    monkeypatch.setenv("JWKS_URL", "https://issuer.example/jwks.json")
    monkeypatch.delenv("JWT_AUDIENCE", raising=False)
    with pytest.raises(RuntimeError, match="JWT_AUDIENCE"):
        verify_jwt(_creds())


def test_missing_jwks_url_raises_runtime_error(monkeypatch):
    monkeypatch.setenv("JWT_AUDIENCE", "seekr-api")
    monkeypatch.delenv("JWKS_URL", raising=False)
    with pytest.raises(RuntimeError, match="JWKS_URL"):
        verify_jwt(_creds())


def test_valid_token_returns_payload(monkeypatch, configured_env):
    payload = {"sub": "user-1", "aud": "seekr-api", "roles": ["admin"]}
    monkeypatch.setattr(security, "get_jwks_client", lambda: _FakeJWKSClient())
    monkeypatch.setattr(security.jwt, "decode", lambda *a, **k: payload)

    result = verify_jwt(_creds())
    assert result == payload


def test_expired_token_raises_authentication_error(monkeypatch, configured_env):
    monkeypatch.setattr(security, "get_jwks_client", lambda: _FakeJWKSClient())

    def _raise(*a, **k):
        raise jwt.ExpiredSignatureError("expired")

    monkeypatch.setattr(security.jwt, "decode", _raise)
    with pytest.raises(AuthenticationError, match="expired"):
        verify_jwt(_creds())


def test_wrong_audience_raises_authentication_error(monkeypatch, configured_env):
    monkeypatch.setattr(security, "get_jwks_client", lambda: _FakeJWKSClient())

    def _raise(*a, **k):
        raise jwt.InvalidAudienceError("bad audience")

    monkeypatch.setattr(security.jwt, "decode", _raise)
    with pytest.raises(AuthenticationError, match="Invalid token"):
        verify_jwt(_creds())


def test_bad_signature_raises_authentication_error(monkeypatch, configured_env):
    monkeypatch.setattr(security, "get_jwks_client", lambda: _FakeJWKSClient())

    def _raise(*a, **k):
        raise jwt.InvalidSignatureError("bad signature")

    monkeypatch.setattr(security.jwt, "decode", _raise)
    with pytest.raises(AuthenticationError, match="Invalid token"):
        verify_jwt(_creds())


def test_malformed_token_raises_authentication_error(monkeypatch, configured_env):
    monkeypatch.setattr(security, "get_jwks_client", lambda: _FakeJWKSClient())

    def _raise(*a, **k):
        raise jwt.DecodeError("not a jwt")

    monkeypatch.setattr(security.jwt, "decode", _raise)
    with pytest.raises(AuthenticationError, match="Invalid token"):
        verify_jwt(_creds())


def test_jwks_fetch_failure_raises_authentication_error(monkeypatch, configured_env):
    class _FailingClient:
        def get_signing_key_from_jwt(self, token):
            raise jwt.PyJWKClientError("cannot fetch keys")

    monkeypatch.setattr(security, "get_jwks_client", lambda: _FailingClient())
    with pytest.raises(AuthenticationError, match="signing keys"):
        verify_jwt(_creds())
