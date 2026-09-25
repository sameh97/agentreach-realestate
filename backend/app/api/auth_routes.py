"""
POST /api/auth/register  → create account, returns {token, user}
POST /api/auth/login     → returns {token, user}
GET  /api/auth/me        → current user (requires Bearer token)
"""
import asyncio, re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from pymongo.errors import DuplicateKeyError

from app import db
from app.auth import create_token, current_user, hash_password, public_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegisterRequest(BaseModel):
    email:    str
    password: str
    name:     str = ""

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Enter a valid email address")
        return v

    @field_validator("password")
    @classmethod
    def _password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v.encode()) > 72:  # bcrypt's hard input limit
            raise ValueError("Password must be at most 72 bytes")
        return v

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        return v.strip()[:80]


class LoginRequest(BaseModel):
    email:    str
    password: str


def _auth_response(user: dict) -> dict:
    return {"token": create_token(str(user["_id"])), "user": public_user(user)}


@router.post("/register", status_code=201)
async def register(req: RegisterRequest):
    user = {
        "email":         req.email,
        "name":          req.name,
        "password_hash": await asyncio.to_thread(hash_password, req.password),
        "created_at":    datetime.now(timezone.utc),
    }
    try:
        res = await db.users().insert_one(user)
    except DuplicateKeyError:
        raise HTTPException(409, "An account with this email already exists")
    user["_id"] = res.inserted_id
    return _auth_response(user)


@router.post("/login")
async def login(req: LoginRequest):
    user = await db.users().find_one({"email": req.email.strip().lower()})
    if not user or not await asyncio.to_thread(verify_password, req.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")
    return _auth_response(user)


@router.get("/me")
async def me(user: dict = Depends(current_user)):
    return public_user(user)
