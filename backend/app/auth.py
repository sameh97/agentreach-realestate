"""
Auth — password hashing, JWT issue/verify, and the `current_user` dependency.

Tokens are stateless HS256 JWTs signed with JWT_SECRET. Every uvicorn worker
(and every future replica) must share the same secret, so it is read from the
environment — never generated at runtime.
"""
import os, logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import db

logger = logging.getLogger(__name__)

_DEV_SECRET = "dev-insecure-secret-change-me"
JWT_SECRET  = os.getenv("JWT_SECRET", "") or _DEV_SECRET
JWT_ALG     = "HS256"
JWT_TTL     = timedelta(days=int(os.getenv("JWT_TTL_DAYS", "7")))

if JWT_SECRET == _DEV_SECRET:
    logger.warning("[auth] JWT_SECRET is not set — using an insecure dev secret. Set it before deploying.")

_bearer = HTTPBearer(auto_error=False)


# ── Passwords ─────────────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


# ── Tokens ────────────────────────────────────────────────────────────────────

def create_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user_id, "iat": now, "exp": now + JWT_TTL}, JWT_SECRET, algorithm=JWT_ALG)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


# ── Dependency ────────────────────────────────────────────────────────────────

def public_user(user: dict) -> dict:
    return {
        "id":         str(user["_id"]),
        "email":      user["email"],
        "name":       user.get("name", ""),
        "created_at": user["created_at"].isoformat(),
    }


async def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if creds is None:
        raise _unauthorized("Not authenticated")
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALG])
        user_id = ObjectId(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Session expired — please log in again")
    except (jwt.InvalidTokenError, InvalidId, KeyError):
        raise _unauthorized("Invalid token")

    user = await db.users().find_one({"_id": user_id})
    if user is None:
        raise _unauthorized("User no longer exists")
    return user
