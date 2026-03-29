from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from fastapi import Depends, HTTPException, Request

from app import database
from app.config import get_settings
from app.security import create_access_token, create_refresh_token, decode_jwt, hash_password, verify_password


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PASSWORD_MIN_LENGTH = 10
ALLOWED_ROLES = frozenset({database.DEFAULT_USER_ROLE, database.ADMIN_ROLE})


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    email: str
    full_name: str
    role: str


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


def _normalize_role(role: str | None) -> str:
    normalized = (role or database.DEFAULT_USER_ROLE).strip().lower()
    if not normalized:
        return database.DEFAULT_USER_ROLE
    return normalized if normalized in ALLOWED_ROLES else database.DEFAULT_USER_ROLE


def validate_role_value(role: str) -> str:
    normalized = (role or "").strip().lower()
    if normalized not in ALLOWED_ROLES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": "Role must be either 'student' or 'admin'.",
            },
        )
    return normalized


def serialize_user(user: dict[str, object]) -> dict[str, str]:
    return {
        "id": str(user["id"]),
        "email": str(user["email"]),
        "full_name": str(user["full_name"]),
        "role": _normalize_role(user.get("role") if isinstance(user, dict) else None),
    }


def list_users() -> list[dict[str, str]]:
    return [serialize_user(user) for user in database.list_users()]


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
        role=database.DEFAULT_USER_ROLE,
    )
    return issue_session(
        user_id=user_id,
        email=normalized_email,
        full_name=cleaned_full_name,
        role=database.DEFAULT_USER_ROLE,
    )


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
        role=_normalize_role(user.get("role")),
    )


def issue_session(*, user_id: str, email: str, full_name: str, role: str) -> dict[str, object]:
    settings = get_settings()
    access_token = create_access_token(subject=user_id, email=email, role=role)
    refresh_token, refresh_expires_at = create_refresh_token(
        subject=user_id,
        email=email,
        role=role,
    )
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
            "role": role,
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
        role=_normalize_role(user.get("role")),
    )


def update_user_role(*, user_id: str, role: str) -> dict[str, str]:
    normalized_role = validate_role_value(role)
    user = database.fetch_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "user_not_found",
                "message": "User was not found.",
            },
        )

    updated_user = database.update_user_role(
        user_id=str(user["id"]),
        role=normalized_role,
    )
    if updated_user is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "user_not_found",
                "message": "User was not found.",
            },
        )
    return serialize_user(updated_user)


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
        role=_normalize_role(user.get("role")),
    )


def require_role(required_roles: list[str]):
    allowed_roles = {
        role.strip().lower()
        for role in required_roles
        if role.strip()
    }
    if not allowed_roles:
        raise ValueError("At least one role must be provided.")

    def dependency(
        current_user: AuthenticatedUser = Depends(require_authenticated_user),
    ) -> AuthenticatedUser:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "forbidden",
                    "message": "You do not have permission to access this resource.",
                },
            )
        return current_user

    return dependency