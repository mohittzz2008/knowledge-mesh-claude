"""FastAPI Authentication Dependency & Clerk User Mapping.

Two modes:

* Production (``CLERK_JWKS_URL`` set): the Clerk session JWT in
  ``Authorization: Bearer <token>`` is verified (signature, expiry, optional
  issuer) and its ``sub`` claim is the Clerk user id. Headers claiming an id
  are ignored.
* Development (no ``CLERK_JWKS_URL``): the legacy behaviour - trust
  ``X-Clerk-User-Id``. Anyone can forge that header, so it is only allowed
  while ``ALLOW_INSECURE_DEV_AUTH`` is true (the default, for local use) and a
  warning is logged once.
"""

import logging
from functools import lru_cache
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import DeveloperProfile, User

logger = logging.getLogger(__name__)
_warned_insecure = False


@lru_cache(maxsize=1)
def _jwks_client(url: str) -> "jwt.PyJWKClient":
    return jwt.PyJWKClient(url, cache_keys=True)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _clerk_id_from_jwt(token: str) -> str:
    try:
        signing_key = _jwks_client(settings.clerk_jwks_url).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer or None,
            options={"verify_aud": False, "verify_iss": bool(settings.clerk_issuer)},
        )
    except jwt.PyJWTError as err:
        raise _unauthorized("Invalid or expired session token.") from err
    sub = claims.get("sub")
    if not sub:
        raise _unauthorized("Session token has no subject.")
    return str(sub)


def _extract_clerk_id(request: Request) -> str:
    global _warned_insecure

    auth_header = request.headers.get("Authorization") or ""
    bearer: Optional[str] = None
    if auth_header.lower().startswith("bearer "):
        candidate = auth_header.split(" ", 1)[1].strip()
        if candidate and candidate not in ("undefined", "null"):
            bearer = candidate

    if settings.clerk_jwks_url:
        if not bearer:
            raise _unauthorized("Authentication required. Provide a Clerk session token.")
        return _clerk_id_from_jwt(bearer)

    if not settings.allow_insecure_dev_auth:
        raise _unauthorized("Server authentication is not configured (set CLERK_JWKS_URL).")

    if not _warned_insecure:
        logger.warning(
            "CLERK_JWKS_URL is not set: trusting the X-Clerk-User-Id header. "
            "This is insecure; configure Clerk JWT verification before deploying."
        )
        _warned_insecure = True

    clerk_id = request.headers.get("X-Clerk-User-Id") or bearer
    if not clerk_id:
        raise _unauthorized(
            "Authentication required. Please provide a valid Clerk User ID or Authorization token."
        )
    return clerk_id


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the authenticated Clerk user to a PostgreSQL User (creating it on first login)."""
    clerk_id = _extract_clerk_id(request)

    user = db.query(User).filter(User.clerk_user_id == clerk_id).first()
    if user:
        return user

    try:
        user = User(
            clerk_user_id=clerk_id,
            email=f"{clerk_id.lower()}@knowledgemesh.ai",
            full_name="Knowledge Mesh Developer",
        )
        db.add(user)
        db.flush()  # assigns user.id without committing a half-created account
        db.add(DeveloperProfile(user_id=user.id))
        db.commit()  # user and profile are created atomically
    except IntegrityError:
        # A parallel request (the dashboard fires several at once) created the account first.
        db.rollback()
        existing = db.query(User).filter(User.clerk_user_id == clerk_id).first()
        if existing is None:
            raise
        return existing
    db.refresh(user)
    return user
