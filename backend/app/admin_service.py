from __future__ import annotations

import re
from uuid import uuid4

from fastapi import HTTPException

from app import database
from app.auth_service import normalize_email, validate_password
from app.security import hash_password


ROLE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")


def _raise_not_found(*, code: str, message: str) -> None:
    raise HTTPException(status_code=404, detail={"code": code, "message": message})


def _raise_validation(message: str) -> None:
    raise HTTPException(
        status_code=422,
        detail={
            "code": "validation_error",
            "message": message,
        },
    )


def _normalize_role_name(role_name: str) -> str:
    normalized = (role_name or "").strip().lower()
    if not ROLE_NAME_PATTERN.match(normalized):
        _raise_validation(
            "Role name must start with a letter and use only lowercase letters, numbers, hyphens, or underscores."
        )
    return normalized


def _normalize_permission_codes(permission_codes: list[str]) -> list[str]:
    allowed_codes = set(database.KNOWN_PERMISSION_DEFINITIONS)
    normalized_codes: list[str] = []
    invalid_codes: list[str] = []
    for code in permission_codes:
        normalized = str(code or "").strip().lower()
        if not normalized:
            continue
        if normalized not in allowed_codes:
            invalid_codes.append(normalized)
            continue
        normalized_codes.append(normalized)
    if invalid_codes:
        invalid = ", ".join(sorted(set(invalid_codes)))
        _raise_validation(f"Unknown permission codes: {invalid}")
    return sorted(set(normalized_codes))


def _log_activity(
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_user_id: str | None,
    target_user_id: str | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    database.insert_activity_log(
        log_id=uuid4().hex,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        metadata=dict(metadata or {}),
    )


def get_dashboard_summary() -> dict[str, int]:
    return database.get_admin_dashboard_summary()


def get_permission_catalog() -> list[dict[str, str]]:
    return [
        {
            "code": code,
            "label": payload["label"],
            "description": payload["description"],
        }
        for code, payload in sorted(database.KNOWN_PERMISSION_DEFINITIONS.items())
    ]


def list_admin_users() -> list[dict[str, object]]:
    return database.list_admin_users()


def create_admin_user(
    *,
    actor_user_id: str,
    email: str,
    password: str,
    full_name: str,
    role: str,
    is_active: bool = True,
) -> dict[str, object]:
    normalized_email = normalize_email(email)
    cleaned_full_name = (full_name or "").strip()
    if not cleaned_full_name:
        _raise_validation("Full name is required.")
    validate_password(password)

    normalized_role = _normalize_role_name(role)
    if database.fetch_role(normalized_role) is None:
        _raise_validation("Role was not found.")
    if database.fetch_user_by_email(normalized_email) is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "email_in_use",
                "message": "Email address already exists.",
            },
        )

    password_salt, password_hash = hash_password(password)
    user_id = str(uuid4())
    database.insert_user(
        user_id=user_id,
        email=normalized_email,
        full_name=cleaned_full_name,
        password_salt=password_salt,
        password_hash=password_hash,
        role=normalized_role,
    )
    if not is_active:
        database.update_user_admin_fields(user_id=user_id, is_active=False)

    _log_activity(
        action="users.created",
        entity_type="user",
        entity_id=user_id,
        actor_user_id=actor_user_id,
        target_user_id=user_id,
        metadata={
            "email": normalized_email,
            "role": normalized_role,
            "is_active": bool(is_active),
        },
    )
    return get_admin_user(user_id)


def get_admin_user(user_id: str) -> dict[str, object]:
    user = database.fetch_admin_user(user_id)
    if user is None:
        _raise_not_found(code="user_not_found", message="User was not found.")
    return user


def update_admin_user(
    *,
    actor_user_id: str,
    user_id: str,
    role: str | None = None,
    is_active: bool | None = None,
) -> dict[str, object]:
    existing_user = database.fetch_user_by_id(user_id)
    if existing_user is None:
        _raise_not_found(code="user_not_found", message="User was not found.")

    normalized_role: str | None = None
    if role is not None:
        normalized_role = _normalize_role_name(role)
        if database.fetch_role(normalized_role) is None:
            _raise_validation("Role was not found.")

    updated = database.update_user_admin_fields(
        user_id=user_id,
        role=normalized_role,
        is_active=is_active,
    )
    if updated is None:
        _raise_not_found(code="user_not_found", message="User was not found.")

    _log_activity(
        action="users.updated",
        entity_type="user",
        entity_id=user_id,
        actor_user_id=actor_user_id,
        target_user_id=user_id,
        metadata={
            "previous_role": str(existing_user.get("role") or database.DEFAULT_USER_ROLE),
            "new_role": normalized_role or str(existing_user.get("role") or database.DEFAULT_USER_ROLE),
            "previous_is_active": bool(existing_user.get("is_active", 1)),
            "new_is_active": bool(updated.get("is_active", existing_user.get("is_active", 1))),
        },
    )
    return get_admin_user(user_id)


def update_user_permissions(
    *,
    actor_user_id: str,
    user_id: str,
    granted_permissions: list[str],
    revoked_permissions: list[str],
) -> dict[str, object]:
    user = database.fetch_user_by_id(user_id)
    if user is None:
        _raise_not_found(code="user_not_found", message="User was not found.")

    granted = set(_normalize_permission_codes(granted_permissions))
    revoked = set(_normalize_permission_codes(revoked_permissions))
    granted -= revoked
    overrides = database.upsert_user_permission_overrides(
        user_id=user_id,
        granted_permissions=sorted(granted),
        revoked_permissions=sorted(revoked),
    )
    _log_activity(
        action="users.permissions_updated",
        entity_type="user_permissions",
        entity_id=user_id,
        actor_user_id=actor_user_id,
        target_user_id=user_id,
        metadata={
            "granted_permissions": overrides["granted_permissions"],
            "revoked_permissions": overrides["revoked_permissions"],
        },
    )
    return get_admin_user(user_id)


def list_roles() -> list[dict[str, object]]:
    return database.list_roles()


def create_role(
    *,
    actor_user_id: str,
    role_name: str,
    display_name: str,
    description: str,
    permissions: list[str],
) -> dict[str, object]:
    normalized_role = _normalize_role_name(role_name)
    if database.fetch_role(normalized_role) is not None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "role_exists",
                "message": "Role already exists.",
            },
        )
    cleaned_display_name = (display_name or "").strip()
    if not cleaned_display_name:
        _raise_validation("Display name is required.")

    role = database.upsert_role(
        role_name=normalized_role,
        display_name=cleaned_display_name,
        description=(description or "").strip(),
        permissions=_normalize_permission_codes(permissions),
        is_system=False,
    )
    _log_activity(
        action="roles.created",
        entity_type="role",
        entity_id=normalized_role,
        actor_user_id=actor_user_id,
        metadata={"permissions": role["permissions"]},
    )
    return role


def update_role(
    *,
    actor_user_id: str,
    role_name: str,
    display_name: str | None = None,
    description: str | None = None,
    permissions: list[str] | None = None,
) -> dict[str, object]:
    existing_role = database.fetch_role(role_name)
    if existing_role is None:
        _raise_not_found(code="role_not_found", message="Role was not found.")

    cleaned_display_name = (
        (display_name or "").strip()
        if display_name is not None
        else str(existing_role["display_name"])
    )
    if not cleaned_display_name:
        _raise_validation("Display name is required.")

    role = database.upsert_role(
        role_name=str(existing_role["name"]),
        display_name=cleaned_display_name,
        description=(
            (description or "").strip()
            if description is not None
            else str(existing_role.get("description") or "")
        ),
        permissions=(
            _normalize_permission_codes(permissions)
            if permissions is not None
            else list(existing_role.get("permissions", []))
        ),
        is_system=bool(existing_role.get("is_system")),
    )
    _log_activity(
        action="roles.updated",
        entity_type="role",
        entity_id=str(existing_role["name"]),
        actor_user_id=actor_user_id,
        metadata={"permissions": role["permissions"]},
    )
    return role


def get_activity_logs(
    *,
    limit: int = 50,
    actor_user_id: str | None = None,
    target_user_id: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
) -> list[dict[str, object]]:
    bounded_limit = max(1, min(limit, 100))
    return database.list_activity_logs(
        limit=bounded_limit,
        actor_user_id=(actor_user_id or "").strip() or None,
        target_user_id=(target_user_id or "").strip() or None,
        action=(action or "").strip() or None,
        entity_type=(entity_type or "").strip() or None,
    )
