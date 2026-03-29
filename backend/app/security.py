from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config import get_settings


PBKDF2_ITERATIONS = 310000


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str, *, salt: str | None = None) -> tuple[str, str]:
    raw_salt = _b64url_decode(salt) if salt else os.urandom(16)
    derived_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        raw_salt,
        PBKDF2_ITERATIONS,
    )
    return _b64url_encode(raw_salt), _b64url_encode(derived_key)


def verify_password(password: str, salt: str, password_hash: str) -> bool:
    _, computed_hash = hash_password(password, salt=salt)
    return hmac.compare_digest(computed_hash, password_hash)


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_access_token(*, subject: str, email: str) -> str:
    settings = get_settings()
    return encode_jwt(
        {
            "sub": subject,
            "email": email,
            "type": "access",
            "exp": int((utc_now() + timedelta(seconds=settings.access_token_ttl_seconds)).timestamp()),
        }
    )


def create_refresh_token(*, subject: str, email: str) -> tuple[str, datetime]:
    settings = get_settings()
    expires_at = utc_now() + timedelta(seconds=settings.refresh_token_ttl_seconds)
    token = encode_jwt(
        {
            "sub": subject,
            "email": email,
            "type": "refresh",
            "exp": int(expires_at.timestamp()),
        }
    )
    return token, expires_at


def encode_jwt(payload: dict[str, Any]) -> str:
    settings = get_settings()
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = "{}.{}".format(
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    )
    signature = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(signature)}"


def decode_jwt(token: str, *, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Malformed token.")

    header_segment, payload_segment, signature_segment = parts
    signing_input = f"{header_segment}.{payload_segment}"
    expected_signature = hmac.new(
        settings.jwt_secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()

    if not hmac.compare_digest(_b64url_encode(expected_signature), signature_segment):
        raise ValueError("Invalid token signature.")

    payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    token_type = str(payload.get("type", ""))
    if token_type != expected_type:
        raise ValueError("Invalid token type.")

    exp = int(payload.get("exp", 0))
    if exp <= int(utc_now().timestamp()):
        raise ValueError("Token has expired.")

    return payload