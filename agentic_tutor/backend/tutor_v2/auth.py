"""HTTP identity verification; independent of the tutoring engine."""
from __future__ import annotations

import os
from typing import Protocol

import jwt


class AuthenticationError(ValueError):
    """Missing, invalid, expired, or mismatched identity."""


class IdentityVerifier(Protocol):
    def verify(self, authorization: str | None, user_id: str | None) -> str: ...


class DevVerifier:
    """Explicit AUTH_MODE=dev only. Never silently selected for missing secrets."""

    def verify(self, authorization: str | None, user_id: str | None) -> str:
        if not user_id or not user_id.strip():
            raise AuthenticationError("X-User-Id is required")
        return user_id.strip()


class SupabaseVerifier:
    def __init__(self, *, secret: str | None = None, jwks_url: str | None = None,
                 issuer: str | None = None, audience: str = "authenticated") -> None:
        if not secret and not jwks_url:
            raise ValueError("Supabase auth requires SUPABASE_JWT_SECRET or SUPABASE_JWKS_URL")
        self.secret, self.issuer, self.audience = secret, issuer, audience
        self.jwks = jwt.PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300, timeout=5) if jwks_url else None

    def verify(self, authorization: str | None, user_id: str | None) -> str:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip() or not user_id:
            raise AuthenticationError("Bearer token and X-User-Id are required")
        try:
            algorithm = jwt.get_unverified_header(token).get("alg")
            # The untrusted header selects only between explicitly configured key types.
            # Never let a public key be interpreted as an HMAC secret.
            if algorithm == "HS256" and self.secret:
                key, algorithms = self.secret, ["HS256"]
            elif algorithm in {"RS256", "ES256"} and self.jwks:
                key, algorithms = self.jwks.get_signing_key_from_jwt(token).key, [algorithm]
            else:
                raise AuthenticationError("Unsupported signing algorithm")
            claims = jwt.decode(token, key, algorithms=algorithms, audience=self.audience,
                                issuer=self.issuer, options={"require": ["exp", "sub", "aud"]})
            subject = claims["sub"]
            if not isinstance(subject, str) or not subject.strip() or subject != user_id:
                raise AuthenticationError("Token subject does not match X-User-Id")
            return subject
        except (jwt.PyJWTError, ValueError, TypeError) as exc:
            raise AuthenticationError("Invalid or expired credentials") from exc


def verifier_from_env() -> IdentityVerifier:
    mode = os.getenv("AUTH_MODE", "supabase").lower()
    if mode == "dev":
        return DevVerifier()
    if mode != "supabase":
        raise ValueError("AUTH_MODE must be supabase or dev")
    project = os.getenv("SUPABASE_URL", "").rstrip("/")
    issuer = os.getenv("SUPABASE_JWT_ISSUER") or (f"{project}/auth/v1" if project else None)
    return SupabaseVerifier(secret=os.getenv("SUPABASE_JWT_SECRET"),
                            jwks_url=os.getenv("SUPABASE_JWKS_URL") or (
                                f"{issuer}/.well-known/jwks.json" if issuer else None),
                            issuer=issuer, audience=os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated"))
