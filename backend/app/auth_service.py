from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from fastapi import HTTPException, Request

from app import database
from app.config import get_settings
from app.security import create_access_token, create_refresh_token, decode_jwt, hash_password, verify_password


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN_LENGTH = 10


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: str
    full_name: str


def _raise_auth_error(message: str = "Authentication failed.") -> None:
    raise HTTPException(status_code=401, detail={"code": "auth_error", "message": message})


def normalize_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if not normalized or not EMAIL_PATTERN.match(normalized):
        raise HTTPException(status_code=422, detail={"code": "validation_error", "message": "A valid email address is required."})
    return normalized


def validate_password(password: str) -> str:
    cleaned = password or ""
    if len(cleaned) < PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": f"Password must be at least {PASSWORD_MIN_LENGTH} characters long.",
            },
        )
    return cleaned


def register_user(*, email: str, password: str, full_name: str) -> dict[str, object]:
    normalized_email = normalize_email(email)
    cleaned_full_name = (full_name or "").strip()
    if not cleaned_full_name:
        raise HTTPException(status_code=422, detail={"code": "validation_error", "message": "Full name is required."})
    validate_password(password)

    if database.fetch_user_by_email(normalized_email) is not None:
        raise HTTPException(status_code=409, detail={"code": "email_in_use", "message": "Email address already exists."})

    password_salt, password_hash = hash_password(password)
    user_id = str(uuid4())
    database.insert_user(
        user_id=user_id,
        email=normalized_email,
        full_name=cleaned_full_name,
        password_salt=password_salt,
        password_hash=password_hash,
    )
    return issue_session(user_id=user_id, email=normalized_email, full_name=cleaned_full_name)


def authenticate_user(*, email: str, password: str) -> dict[str, object]:
    normalized_email = normalize_email(email)
    user = database.fetch_user_by_email(normalized_email)
    if user is None or not verify_password(password, user["password_salt"], user["password_hash"]):
        _raise_auth_error("Invalid email or password.")

    if not bool(user.get("is_active", 1)):
        _raise_auth_error("User account is disabled.")

    database.update_user_last_login(str(user["id"]))
    return issue_session(
        user_id=str(user["id"]),
        email=str(user["email"]),
        full_name=str(user["full_name"]),
    )


def issue_session(*, user_id: str, email: str, full_name: str) -> dict[str, object]:
    settings = get_settings()
    access_token = create_access_token(subject=user_id, email=email)
    refresh_token, refresh_expires_at = create_refresh_token(subject=user_id, email=email)
    database.store_refresh_token(token=refresh_token, user_id=user_id, expires_at=refresh_expires_at)
    access_expires_at = int((database.utc_now() + timedelta(seconds=settings.access_token_ttl_seconds)).timestamp())
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "access_expires_at": access_expires_at,
        "refresh_expires_at": int(refresh_expires_at.timestamp()),
        "user": {
            "id": user_id,
            "email": email,
            "full_name": full_name,
        },
    }


def refresh_session(refresh_token: str) -> dict[str, object]:
    token = (refresh_token or "").strip()
    if not token:
        _raise_auth_error("Refresh token is required.")
    payload = decode_jwt(token, expected_type="refresh")
    if not database.is_refresh_token_active(token):
        _raise_auth_error("Refresh token is invalid or revoked.")

    user = database.fetch_user_by_id(str(payload["sub"]))
    if user is None:
        _raise_auth_error("User not found.")

    database.revoke_refresh_token(token)
    return issue_session(
        user_id=str(user["id"]),
        email=str(user["email"]),
        full_name=str(user["full_name"]),
    )


def require_authenticated_user(request: Request) -> AuthenticatedUser:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        _raise_auth_error("Bearer token is required.")

    payload = decode_jwt(token.strip(), expected_type="access")
    user = database.fetch_user_by_id(str(payload["sub"]))
    if user is None or not bool(user.get("is_active", 1)):
        _raise_auth_error("User account is unavailable.")

    return AuthenticatedUser(
        user_id=str(user["id"]),
        email=str(user["email"]),
        full_name=str(user["full_name"]),
    )