from __future__ import annotations

import base64
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from app.config import get_settings
from app.security import hash_value, utc_now


DEFAULT_USER_ROLE = "student"
ADMIN_ROLE = "admin"
ADMIN_ACCESS_PERMISSION = "admin.access"
ADMIN_SUMMARY_PERMISSION = "admin.summary.read"
USERS_READ_PERMISSION = "users.read"
USERS_MANAGE_PERMISSION = "users.manage"
ROLES_READ_PERMISSION = "roles.read"
ROLES_MANAGE_PERMISSION = "roles.manage"
ACTIVITY_READ_PERMISSION = "activity.read"
ENGAGEMENT_MANAGE_PERMISSION = "engagement.manage"

DEFAULT_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    DEFAULT_USER_ROLE: (),
    ADMIN_ROLE: (
        ADMIN_ACCESS_PERMISSION,
        ADMIN_SUMMARY_PERMISSION,
        USERS_READ_PERMISSION,
        USERS_MANAGE_PERMISSION,
        ROLES_READ_PERMISSION,
        ROLES_MANAGE_PERMISSION,
        ACTIVITY_READ_PERMISSION,
        ENGAGEMENT_MANAGE_PERMISSION,
    ),
}

KNOWN_PERMISSION_DEFINITIONS: dict[str, dict[str, str]] = {
    ADMIN_ACCESS_PERMISSION: {
        "label": "Admin access",
        "description": "Access administrative endpoints and dashboard views.",
    },
    ADMIN_SUMMARY_PERMISSION: {
        "label": "Admin summary",
        "description": "Read administrative summary and platform metrics.",
    },
    USERS_READ_PERMISSION: {
        "label": "Read users",
        "description": "View users, their roles, and effective permissions.",
    },
    USERS_MANAGE_PERMISSION: {
        "label": "Manage users",
        "description": "Change user role, activation state, and permission overrides.",
    },
    ROLES_READ_PERMISSION: {
        "label": "Read roles",
        "description": "View system and custom roles with their permissions.",
    },
    ROLES_MANAGE_PERMISSION: {
        "label": "Manage roles",
        "description": "Create and update roles and their permission sets.",
    },
    ACTIVITY_READ_PERMISSION: {
        "label": "Read activity log",
        "description": "Browse recent authentication and administrative activity.",
    },
    ENGAGEMENT_MANAGE_PERMISSION: {
        "label": "Manage engagement",
        "description": "Create engagement content for student notifications.",
    },
}


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode_json_list(raw_value: str | None) -> list[str]:
    try:
        payload = json.loads(raw_value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    items: list[str] = []
    for item in payload:
        text = str(item or "").strip()
        if text:
            items.append(text)
    return items


def _encode_json_list(items: list[str] | tuple[str, ...]) -> str:
    return json.dumps(sorted({str(item).strip() for item in items if str(item).strip()}), ensure_ascii=False)


def _seed_default_roles(connection: sqlite3.Connection) -> None:
    now = _timestamp()
    for role_name, permissions in DEFAULT_ROLE_PERMISSIONS.items():
        connection.execute(
            """
            INSERT INTO roles (name, display_name, description, permissions_json, is_system, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                display_name = excluded.display_name,
                description = excluded.description,
                permissions_json = excluded.permissions_json,
                is_system = 1,
                updated_at = excluded.updated_at
            """,
            (
                role_name,
                role_name.replace("_", " ").title(),
                "System role",
                _encode_json_list(permissions),
                now,
                now,
            ),
        )


def get_connection() -> sqlite3.Connection:
    settings = get_settings()
    connection = sqlite3.connect(settings.db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def connection_scope() -> Iterator[sqlite3.Connection]:
    connection = get_connection()
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_database() -> None:
    with connection_scope() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                full_name TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_login_at TEXT
            );

            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                revoked_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS feedback_events (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                question_hash TEXT NOT NULL,
                answer_hash TEXT NOT NULL,
                helpful INTEGER NOT NULL,
                language TEXT NOT NULL,
                sources_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                route_mode TEXT NOT NULL DEFAULT '',
                question_text TEXT NOT NULL DEFAULT '',
                answer_text TEXT NOT NULL DEFAULT '',
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS rate_limit_windows (
                bucket_key TEXT PRIMARY KEY,
                window_started_at INTEGER NOT NULL,
                request_count INTEGER NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS student_profiles (
                user_id TEXT PRIMARY KEY,
                major TEXT NOT NULL DEFAULT '',
                academic_level TEXT NOT NULL DEFAULT '',
                track TEXT NOT NULL DEFAULT '',
                interests_json TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS live_content_items (
                id TEXT PRIMARY KEY,
                content_type TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                link_url TEXT NOT NULL DEFAULT '',
                target_major TEXT NOT NULL DEFAULT '',
                target_level TEXT NOT NULL DEFAULT '',
                tags_json TEXT NOT NULL DEFAULT '[]',
                priority INTEGER NOT NULL DEFAULT 0,
                is_active INTEGER NOT NULL DEFAULT 1,
                starts_at TEXT,
                ends_at TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(created_by) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                content_item_id TEXT,
                priority INTEGER NOT NULL DEFAULT 0,
                is_read INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                read_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY(content_item_id) REFERENCES live_content_items(id) ON DELETE SET NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_user_content_category
            ON notifications(user_id, content_item_id, category);

            CREATE INDEX IF NOT EXISTS idx_notifications_user_read_created
            ON notifications(user_id, is_read, created_at DESC);

            CREATE TABLE IF NOT EXISTS notification_preferences (
                user_id TEXT PRIMARY KEY,
                enable_push INTEGER NOT NULL DEFAULT 1,
                enable_in_app INTEGER NOT NULL DEFAULT 1,
                categories_json TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS notification_device_tokens (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                platform TEXT NOT NULL,
                device_name TEXT NOT NULL DEFAULT '',
                app_version TEXT NOT NULL DEFAULT '',
                locale TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                invalidated_at TEXT,
                invalidation_reason TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_notification_device_tokens_user_active
            ON notification_device_tokens(user_id, invalidated_at, updated_at DESC);

            CREATE TABLE IF NOT EXISTS roles (
                name TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                permissions_json TEXT NOT NULL DEFAULT '[]',
                is_system INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS user_permission_overrides (
                user_id TEXT PRIMARY KEY,
                granted_permissions_json TEXT NOT NULL DEFAULT '[]',
                revoked_permissions_json TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS activity_logs (
                id TEXT PRIMARY KEY,
                actor_user_id TEXT,
                target_user_id TEXT,
                action TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                FOREIGN KEY(actor_user_id) REFERENCES users(id) ON DELETE SET NULL,
                FOREIGN KEY(target_user_id) REFERENCES users(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_activity_logs_created_at
            ON activity_logs(created_at DESC, id DESC);

            CREATE INDEX IF NOT EXISTS idx_activity_logs_target_user
            ON activity_logs(target_user_id, created_at DESC, id DESC);
            """
        )
        user_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        if "role" not in user_columns:
            connection.execute(
                "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'student'"
            )

        feedback_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(feedback_events)").fetchall()
        }
        for col, definition in [
            ("reason", "TEXT NOT NULL DEFAULT ''"),
            ("route_mode", "TEXT NOT NULL DEFAULT ''"),
            ("question_text", "TEXT NOT NULL DEFAULT ''"),
            ("answer_text", "TEXT NOT NULL DEFAULT ''"),
        ]:
            if col not in feedback_columns:
                connection.execute(f"ALTER TABLE feedback_events ADD COLUMN {col} {definition}")

        profile_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(student_profiles)").fetchall()
        }
        if "track" not in profile_columns:
            connection.execute("ALTER TABLE student_profiles ADD COLUMN track TEXT NOT NULL DEFAULT ''")

        notification_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(notifications)").fetchall()
        }
        for col, definition in [
            ("route_type", "TEXT NOT NULL DEFAULT 'engagement'"),
            ("route_payload_json", "TEXT NOT NULL DEFAULT '{}'"),
            ("delivered_at", "TEXT"),
            ("push_status", "TEXT NOT NULL DEFAULT 'pending'"),
            ("last_delivery_error", "TEXT"),
        ]:
            if col not in notification_columns:
                connection.execute(f"ALTER TABLE notifications ADD COLUMN {col} {definition}")

        _seed_default_roles(connection)


def fetch_user_by_email(email: str) -> dict[str, Any] | None:
    with connection_scope() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE email = ? LIMIT 1",
            (email,),
        ).fetchone()
    return dict(row) if row else None


def fetch_user_by_id(user_id: str) -> dict[str, Any] | None:
    with connection_scope() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE id = ? LIMIT 1",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def list_users() -> list[dict[str, Any]]:
    with connection_scope() as connection:
        rows = connection.execute(
            "SELECT * FROM users ORDER BY created_at ASC, email ASC",
        ).fetchall()
    return [dict(row) for row in rows]


def list_role_names() -> list[str]:
    with connection_scope() as connection:
        rows = connection.execute(
            "SELECT name FROM roles ORDER BY name ASC",
        ).fetchall()
    return [str(row["name"]) for row in rows]


def fetch_role(role_name: str) -> dict[str, Any] | None:
    normalized_role = (role_name or "").strip().lower()
    if not normalized_role:
        return None
    with connection_scope() as connection:
        row = connection.execute(
            """
            SELECT
                roles.*,
                COUNT(users.id) AS user_count
            FROM roles
            LEFT JOIN users ON users.role = roles.name
            WHERE roles.name = ?
            GROUP BY roles.name, roles.display_name, roles.description,
                     roles.permissions_json, roles.is_system, roles.created_at, roles.updated_at
            LIMIT 1
            """,
            (normalized_role,),
        ).fetchone()
    if row is None:
        return None
    payload = dict(row)
    payload["permissions"] = _decode_json_list(payload.pop("permissions_json", "[]"))
    payload["is_system"] = bool(payload.get("is_system"))
    payload["user_count"] = int(payload.get("user_count") or 0)
    return payload


def list_roles() -> list[dict[str, Any]]:
    with connection_scope() as connection:
        rows = connection.execute(
            """
            SELECT
                roles.*,
                COUNT(users.id) AS user_count
            FROM roles
            LEFT JOIN users ON users.role = roles.name
            GROUP BY roles.name, roles.display_name, roles.description,
                     roles.permissions_json, roles.is_system, roles.created_at, roles.updated_at
            ORDER BY roles.is_system DESC, roles.name ASC
            """
        ).fetchall()
    roles: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["permissions"] = _decode_json_list(payload.pop("permissions_json", "[]"))
        payload["is_system"] = bool(payload.get("is_system"))
        payload["user_count"] = int(payload.get("user_count") or 0)
        roles.append(payload)
    return roles


def upsert_role(
    *,
    role_name: str,
    display_name: str,
    description: str,
    permissions: list[str],
    is_system: bool = False,
) -> dict[str, Any]:
    now = _timestamp()
    normalized_role = (role_name or "").strip().lower()
    with connection_scope() as connection:
        connection.execute(
            """
            INSERT INTO roles (name, display_name, description, permissions_json, is_system, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                display_name = excluded.display_name,
                description = excluded.description,
                permissions_json = excluded.permissions_json,
                is_system = excluded.is_system,
                updated_at = excluded.updated_at
            """,
            (
                normalized_role,
                display_name,
                description,
                _encode_json_list(permissions),
                1 if is_system else 0,
                now,
                now,
            ),
        )
    role = fetch_role(normalized_role)
    if role is None:
        raise RuntimeError("Failed to persist role.")
    return role


def fetch_user_permission_overrides(user_id: str) -> dict[str, Any]:
    with connection_scope() as connection:
        row = connection.execute(
            """
            SELECT user_id, granted_permissions_json, revoked_permissions_json, updated_at
            FROM user_permission_overrides
            WHERE user_id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if row is None:
        return {
            "user_id": user_id,
            "granted_permissions": [],
            "revoked_permissions": [],
            "updated_at": None,
        }
    payload = dict(row)
    return {
        "user_id": payload["user_id"],
        "granted_permissions": _decode_json_list(payload.get("granted_permissions_json")),
        "revoked_permissions": _decode_json_list(payload.get("revoked_permissions_json")),
        "updated_at": payload.get("updated_at"),
    }


def upsert_user_permission_overrides(
    *,
    user_id: str,
    granted_permissions: list[str],
    revoked_permissions: list[str],
) -> dict[str, Any]:
    now = _timestamp()
    with connection_scope() as connection:
        connection.execute(
            """
            INSERT INTO user_permission_overrides (
                user_id, granted_permissions_json, revoked_permissions_json, updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                granted_permissions_json = excluded.granted_permissions_json,
                revoked_permissions_json = excluded.revoked_permissions_json,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                _encode_json_list(granted_permissions),
                _encode_json_list(revoked_permissions),
                now,
            ),
        )
    return fetch_user_permission_overrides(user_id)


def resolve_user_permissions(*, user_id: str, role_name: str | None = None) -> list[str]:
    normalized_role = (role_name or "").strip().lower()
    if not normalized_role:
        user = fetch_user_by_id(user_id)
        normalized_role = str((user or {}).get("role") or DEFAULT_USER_ROLE).strip().lower()
    role = fetch_role(normalized_role)
    role_permissions = set(role.get("permissions", [])) if role else set(DEFAULT_ROLE_PERMISSIONS.get(DEFAULT_USER_ROLE, ()))
    overrides = fetch_user_permission_overrides(user_id)
    granted = set(overrides.get("granted_permissions", []))
    revoked = set(overrides.get("revoked_permissions", []))
    return sorted((role_permissions | granted) - revoked)


def _serialize_admin_user(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    payload = dict(row)
    overrides = fetch_user_permission_overrides(str(payload["id"]))
    role_name = str(payload.get("role") or DEFAULT_USER_ROLE).strip().lower()
    return {
        "id": str(payload["id"]),
        "email": str(payload["email"]),
        "full_name": str(payload["full_name"]),
        "role": role_name,
        "is_active": bool(payload.get("is_active", 1)),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "last_login_at": payload.get("last_login_at"),
        "permissions": resolve_user_permissions(user_id=str(payload["id"]), role_name=role_name),
        "granted_permissions": list(overrides.get("granted_permissions", [])),
        "revoked_permissions": list(overrides.get("revoked_permissions", [])),
    }


def list_admin_users() -> list[dict[str, Any]]:
    with connection_scope() as connection:
        rows = connection.execute(
            "SELECT * FROM users ORDER BY created_at ASC, email ASC",
        ).fetchall()
    return [_serialize_admin_user(row) for row in rows]


def fetch_admin_user(user_id: str) -> dict[str, Any] | None:
    with connection_scope() as connection:
        row = connection.execute(
            "SELECT * FROM users WHERE id = ? LIMIT 1",
            (user_id,),
        ).fetchone()
    return _serialize_admin_user(row) if row else None


def insert_activity_log(
    *,
    log_id: str,
    action: str,
    entity_type: str,
    entity_id: str = "",
    actor_user_id: str | None = None,
    target_user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    created_at = _timestamp()
    with connection_scope() as connection:
        connection.execute(
            """
            INSERT INTO activity_logs (
                id, actor_user_id, target_user_id, action, entity_type, entity_id, metadata_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                actor_user_id,
                target_user_id,
                action,
                entity_type,
                entity_id,
                json.dumps(metadata or {}, ensure_ascii=False),
                created_at,
            ),
        )
    return {
        "id": log_id,
        "actor_user_id": actor_user_id,
        "target_user_id": target_user_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "metadata": metadata or {},
        "created_at": created_at,
    }


def list_activity_logs(
    *,
    limit: int = 50,
    actor_user_id: str | None = None,
    target_user_id: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT id, actor_user_id, target_user_id, action, entity_type, entity_id, metadata_json, created_at
        FROM activity_logs
        WHERE 1 = 1
    """
    params: list[Any] = []
    if actor_user_id:
        query += " AND actor_user_id = ?"
        params.append(actor_user_id)
    if target_user_id:
        query += " AND target_user_id = ?"
        params.append(target_user_id)
    if action:
        query += " AND action = ?"
        params.append(action)
    if entity_type:
        query += " AND entity_type = ?"
        params.append(entity_type)
    query += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(limit)

    with connection_scope() as connection:
        rows = connection.execute(query, tuple(params)).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["metadata"] = json.loads(payload.pop("metadata_json") or "{}")
        items.append(payload)
    return items


def get_admin_dashboard_summary() -> dict[str, int]:
    with connection_scope() as connection:
        user_counts = connection.execute(
            """
            SELECT
                COUNT(*) AS total_users,
                SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active_users,
                SUM(CASE WHEN role = ? THEN 1 ELSE 0 END) AS admin_users,
                SUM(CASE WHEN role = ? THEN 1 ELSE 0 END) AS student_users
            FROM users
            """,
            (ADMIN_ROLE, DEFAULT_USER_ROLE),
        ).fetchone()

        def scalar(query: str, params: tuple[object, ...] = ()) -> int:
            row = connection.execute(query, params).fetchone()
            if row is None:
                return 0
            value = row[0]
            return int(value or 0)

        return {
            "total_users": int((user_counts["total_users"] if user_counts else 0) or 0),
            "active_users": int((user_counts["active_users"] if user_counts else 0) or 0),
            "admin_users": int((user_counts["admin_users"] if user_counts else 0) or 0),
            "student_users": int((user_counts["student_users"] if user_counts else 0) or 0),
            "roles": scalar("SELECT COUNT(*) FROM roles"),
            "activity_logs": scalar("SELECT COUNT(*) FROM activity_logs"),
            "feedback_events": scalar("SELECT COUNT(*) FROM feedback_events"),
            "student_profiles": scalar("SELECT COUNT(*) FROM student_profiles"),
            "live_content_items": scalar("SELECT COUNT(*) FROM live_content_items"),
            "notifications": scalar("SELECT COUNT(*) FROM notifications"),
            "unread_notifications": scalar("SELECT COUNT(*) FROM notifications WHERE is_read = 0"),
            "notification_preferences": scalar("SELECT COUNT(*) FROM notification_preferences"),
            "active_device_tokens": scalar(
                "SELECT COUNT(*) FROM notification_device_tokens WHERE invalidated_at IS NULL"
            ),
            "refresh_tokens": scalar("SELECT COUNT(*) FROM refresh_tokens WHERE revoked_at IS NULL"),
        }


def insert_user(
    *,
    user_id: str,
    email: str,
    full_name: str,
    password_salt: str,
    password_hash: str,
    role: str = DEFAULT_USER_ROLE,
) -> None:
    now = _timestamp()
    with connection_scope() as connection:
        connection.execute(
            """
            INSERT INTO users (id, email, full_name, password_salt, password_hash, role, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, email, full_name, password_salt, password_hash, role, now, now),
        )


def update_user_last_login(user_id: str) -> None:
    now = _timestamp()
    with connection_scope() as connection:
        connection.execute(
            "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
            (now, now, user_id),
        )


def update_user_role(*, user_id: str, role: str) -> dict[str, Any] | None:
    return update_user_admin_fields(user_id=user_id, role=role)


def update_user_admin_fields(
    *,
    user_id: str,
    role: str | None = None,
    is_active: bool | None = None,
) -> dict[str, Any] | None:
    assignments: list[str] = []
    params: list[Any] = []
    now = _timestamp()
    if role is not None:
        assignments.append("role = ?")
        params.append(role)
    if is_active is not None:
        assignments.append("is_active = ?")
        params.append(1 if is_active else 0)
    if not assignments:
        return fetch_user_by_id(user_id)
    assignments.append("updated_at = ?")
    params.append(now)
    params.append(user_id)
    with connection_scope() as connection:
        connection.execute(
            f"UPDATE users SET {', '.join(assignments)} WHERE id = ?",
            tuple(params),
        )
        row = connection.execute(
            "SELECT * FROM users WHERE id = ? LIMIT 1",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def store_refresh_token(*, token: str, user_id: str, expires_at: datetime) -> None:
    with connection_scope() as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO refresh_tokens (token_hash, user_id, expires_at, created_at, revoked_at)
            VALUES (?, ?, ?, ?, NULL)
            """,
            (hash_value(token), user_id, expires_at.isoformat(), _timestamp()),
        )


def revoke_refresh_token(token: str) -> None:
    with connection_scope() as connection:
        connection.execute(
            "UPDATE refresh_tokens SET revoked_at = ? WHERE token_hash = ?",
            (_timestamp(), hash_value(token)),
        )


def is_refresh_token_active(token: str) -> bool:
    with connection_scope() as connection:
        row = connection.execute(
            "SELECT expires_at, revoked_at FROM refresh_tokens WHERE token_hash = ? LIMIT 1",
            (hash_value(token),),
        ).fetchone()
    if row is None:
        return False
    if row["revoked_at"]:
        return False
    return row["expires_at"] > utc_now().isoformat()


def _bounded_feedback_text(value: str, *, limit: int = 280) -> str:
    normalized = " ".join((value or "").strip().split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip()


def insert_feedback(*, feedback_id: str, user_id: str, question: str, answer: str, helpful: bool, language: str, sources: list[dict[str, Any]], reason: str = "", route_mode: str = "") -> None:
    # For unhelpful feedback, store bounded snippets instead of full raw text.
    store_question = _bounded_feedback_text(question) if not helpful else ""
    store_answer = _bounded_feedback_text(answer) if not helpful else ""
    with connection_scope() as connection:
        connection.execute(
            """
            INSERT INTO feedback_events (id, user_id, question_hash, answer_hash, helpful, language, sources_json, created_at, reason, route_mode, question_text, answer_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feedback_id,
                user_id,
                hash_value(question.strip()),
                hash_value(answer.strip()),
                1 if helpful else 0,
                language,
                json.dumps(sources, ensure_ascii=False),
                _timestamp(),
                reason,
                route_mode,
                store_question,
                store_answer,
            ),
        )


def fetch_student_profile(user_id: str) -> dict[str, Any]:
    with connection_scope() as connection:
        row = connection.execute(
            """
            SELECT user_id, major, academic_level, track, interests_json, updated_at
            FROM student_profiles
            WHERE user_id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if row is None:
        return {
            "user_id": user_id,
            "major": "",
            "academic_level": "",
            "track": "",
            "interests": [],
            "updated_at": None,
        }
    payload = dict(row)
    return {
        "user_id": payload["user_id"],
        "major": payload["major"] or "",
        "academic_level": payload["academic_level"] or "",
        "track": payload["track"] or "",
        "interests": json.loads(payload["interests_json"] or "[]"),
        "updated_at": payload["updated_at"],
    }


def upsert_student_profile(*, user_id: str, major: str, academic_level: str, track: str, interests: list[str]) -> dict[str, Any]:
    now = _timestamp()
    with connection_scope() as connection:
        connection.execute(
            """
            INSERT INTO student_profiles (user_id, major, academic_level, track, interests_json, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                major = excluded.major,
                academic_level = excluded.academic_level,
                track = excluded.track,
                interests_json = excluded.interests_json,
                updated_at = excluded.updated_at
            """,
            (user_id, major, academic_level, track, json.dumps(interests, ensure_ascii=False), now),
        )
    return fetch_student_profile(user_id)


def insert_live_content_item(
    *,
    item_id: str,
    content_type: str,
    title: str,
    body: str,
    link_url: str,
    target_major: str,
    target_level: str,
    tags: list[str],
    priority: int,
    starts_at: str | None,
    ends_at: str | None,
    created_by: str,
) -> dict[str, Any]:
    now = _timestamp()
    with connection_scope() as connection:
        connection.execute(
            """
            INSERT INTO live_content_items (
                id, content_type, title, body, link_url, target_major, target_level,
                tags_json, priority, is_active, starts_at, ends_at, created_by, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
            """,
            (
                item_id,
                content_type,
                title,
                body,
                link_url,
                target_major,
                target_level,
                json.dumps(tags, ensure_ascii=False),
                priority,
                starts_at,
                ends_at,
                created_by,
                now,
                now,
            ),
        )
    return fetch_live_content_item(item_id)


def fetch_live_content_item(item_id: str) -> dict[str, Any] | None:
    with connection_scope() as connection:
        row = connection.execute(
            "SELECT * FROM live_content_items WHERE id = ? LIMIT 1",
            (item_id,),
        ).fetchone()
    if row is None:
        return None
    payload = dict(row)
    payload["tags"] = json.loads(payload.pop("tags_json") or "[]")
    return payload


def list_active_live_content(*, now_iso: str, limit: int = 100) -> list[dict[str, Any]]:
    with connection_scope() as connection:
        rows = connection.execute(
            """
            SELECT * FROM live_content_items
            WHERE is_active = 1
              AND (starts_at IS NULL OR starts_at <= ?)
              AND (ends_at IS NULL OR ends_at >= ?)
            ORDER BY priority DESC, created_at DESC
            LIMIT ?
            """,
            (now_iso, now_iso, limit),
        ).fetchall()
    items = []
    for row in rows:
        payload = dict(row)
        payload["tags"] = json.loads(payload.pop("tags_json") or "[]")
        items.append(payload)
    return items


def insert_notification(
    *,
    notification_id: str,
    user_id: str,
    category: str,
    title: str,
    message: str,
    content_item_id: str | None,
    priority: int,
    metadata: dict[str, Any],
    route_type: str,
    route_payload: dict[str, Any],
) -> bool:
    with connection_scope() as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO notifications (
                id, user_id, category, title, message, content_item_id, priority,
                is_read, metadata_json, created_at, read_at, route_type, route_payload_json,
                delivered_at, push_status, last_delivery_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, NULL, ?, ?, NULL, 'pending', NULL)
            """,
            (
                notification_id,
                user_id,
                category,
                title,
                message,
                content_item_id,
                priority,
                json.dumps(metadata, ensure_ascii=False),
                _timestamp(),
                route_type,
                json.dumps(route_payload, ensure_ascii=False),
            ),
        )
    return bool(cursor.rowcount)


def _decode_notification_row(row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    metadata = json.loads(payload.pop("metadata_json") or "{}")
    route = {
        "type": payload.pop("route_type", "engagement") or "engagement",
        "payload": json.loads(payload.pop("route_payload_json", "{}") or "{}"),
    }
    metadata["route"] = route
    payload["metadata"] = metadata
    payload["is_read"] = bool(payload["is_read"])
    return payload


def _encode_feed_cursor(*, priority: int, created_at: str, notification_id: str) -> str:
    raw = f"{priority}|{created_at}|{notification_id}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def _decode_feed_cursor(cursor: str) -> tuple[int, str, str]:
    decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    priority_text, created_at, notification_id = decoded.split("|", 2)
    return int(priority_text), created_at, notification_id


def fetch_notification(notification_id: str, *, user_id: str) -> dict[str, Any] | None:
    with connection_scope() as connection:
        row = connection.execute(
            """
            SELECT id, user_id, category, title, message, content_item_id, priority,
                   is_read, metadata_json, created_at, read_at, route_type, route_payload_json,
                   delivered_at, push_status, last_delivery_error
            FROM notifications
            WHERE id = ? AND user_id = ?
            LIMIT 1
            """,
            (notification_id, user_id),
        ).fetchone()
    return _decode_notification_row(row) if row else None


def list_notifications(
    *,
    user_id: str,
    limit: int = 20,
    unread_only: bool = False,
    cursor: str | None = None,
) -> dict[str, Any]:
    query = """
        SELECT id, user_id, category, title, message, content_item_id, priority,
               is_read, metadata_json, created_at, read_at, route_type, route_payload_json,
               delivered_at, push_status, last_delivery_error
        FROM notifications
        WHERE user_id = ?
    """
    params: list[Any] = [user_id]
    if unread_only:
        query += " AND is_read = 0"
    if cursor:
        cursor_priority, cursor_created_at, cursor_id = _decode_feed_cursor(cursor)
        query += """
         AND (
            priority < ?
            OR (priority = ? AND created_at < ?)
            OR (priority = ? AND created_at = ? AND id < ?)
         )
        """
        params.extend(
            [
                cursor_priority,
                cursor_priority,
                cursor_created_at,
                cursor_priority,
                cursor_created_at,
                cursor_id,
            ]
        )
    query += " ORDER BY priority DESC, created_at DESC, id DESC LIMIT ?"
    params.append(limit + 1)

    with connection_scope() as connection:
        rows = connection.execute(query, tuple(params)).fetchall()
    notifications = [_decode_notification_row(row) for row in rows[:limit]]
    has_more = len(rows) > limit
    next_cursor = None
    if has_more and notifications:
        tail = notifications[-1]
        next_cursor = _encode_feed_cursor(
            priority=int(tail["priority"]),
            created_at=str(tail["created_at"]),
            notification_id=str(tail["id"]),
        )
    return {
        "items": notifications,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


def count_unread_notifications(user_id: str) -> int:
    with connection_scope() as connection:
        row = connection.execute(
            "SELECT COUNT(*) AS total FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
        ).fetchone()
    return int(row["total"]) if row else 0


def mark_notification_as_read(*, user_id: str, notification_id: str) -> bool:
    with connection_scope() as connection:
        cursor = connection.execute(
            """
            UPDATE notifications
            SET is_read = 1, read_at = ?
            WHERE id = ? AND user_id = ? AND is_read = 0
            """,
            (_timestamp(), notification_id, user_id),
        )
    return bool(cursor.rowcount)


def update_notification_delivery(
    *,
    notification_id: str,
    user_id: str,
    push_status: str,
    delivered_at: str | None = None,
    last_delivery_error: str | None = None,
) -> None:
    with connection_scope() as connection:
        connection.execute(
            """
            UPDATE notifications
            SET push_status = ?, delivered_at = ?, last_delivery_error = ?
            WHERE id = ? AND user_id = ?
            """,
            (push_status, delivered_at, last_delivery_error, notification_id, user_id),
        )


def fetch_notification_preferences(user_id: str) -> dict[str, Any]:
    with connection_scope() as connection:
        row = connection.execute(
            """
            SELECT user_id, enable_push, enable_in_app, categories_json, updated_at
            FROM notification_preferences
            WHERE user_id = ?
            LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    if row is None:
        return {
            "user_id": user_id,
            "enable_push": True,
            "enable_in_app": True,
            "categories": [],
            "updated_at": None,
        }
    payload = dict(row)
    return {
        "user_id": payload["user_id"],
        "enable_push": bool(payload["enable_push"]),
        "enable_in_app": bool(payload["enable_in_app"]),
        "categories": json.loads(payload["categories_json"] or "[]"),
        "updated_at": payload["updated_at"],
    }


def upsert_notification_preferences(
    *,
    user_id: str,
    enable_push: bool,
    enable_in_app: bool,
    categories: list[dict[str, Any]],
) -> dict[str, Any]:
    now = _timestamp()
    with connection_scope() as connection:
        connection.execute(
            """
            INSERT INTO notification_preferences (user_id, enable_push, enable_in_app, categories_json, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                enable_push = excluded.enable_push,
                enable_in_app = excluded.enable_in_app,
                categories_json = excluded.categories_json,
                updated_at = excluded.updated_at
            """,
            (
                user_id,
                1 if enable_push else 0,
                1 if enable_in_app else 0,
                json.dumps(categories, ensure_ascii=False),
                now,
            ),
        )
    return fetch_notification_preferences(user_id)


def upsert_notification_device_token(
    *,
    token_id: str,
    user_id: str,
    token: str,
    platform: str,
    device_name: str,
    app_version: str,
    locale: str,
) -> dict[str, Any]:
    now = _timestamp()
    token_hash = hash_value(token)
    with connection_scope() as connection:
        connection.execute(
            """
            INSERT INTO notification_device_tokens (
                id, user_id, token, token_hash, platform, device_name, app_version,
                locale, created_at, updated_at, last_seen_at, invalidated_at, invalidation_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            ON CONFLICT(token_hash) DO UPDATE SET
                user_id = excluded.user_id,
                token = excluded.token,
                platform = excluded.platform,
                device_name = excluded.device_name,
                app_version = excluded.app_version,
                locale = excluded.locale,
                updated_at = excluded.updated_at,
                last_seen_at = excluded.last_seen_at,
                invalidated_at = NULL,
                invalidation_reason = NULL
            """,
            (
                token_id,
                user_id,
                token,
                token_hash,
                platform,
                device_name,
                app_version,
                locale,
                now,
                now,
                now,
            ),
        )
        row = connection.execute(
            """
            SELECT id, platform, device_name, app_version, locale, created_at, updated_at,
                   last_seen_at, invalidated_at, invalidation_reason
            FROM notification_device_tokens
            WHERE token_hash = ?
            LIMIT 1
            """,
            (token_hash,),
        ).fetchone()
    payload = dict(row) if row else {}
    payload["is_active"] = payload.get("invalidated_at") is None
    return payload


def delete_notification_device_token(*, user_id: str, token_id: str) -> bool:
    with connection_scope() as connection:
        cursor = connection.execute(
            "DELETE FROM notification_device_tokens WHERE id = ? AND user_id = ?",
            (token_id, user_id),
        )
    return bool(cursor.rowcount)


def list_active_notification_device_tokens(user_id: str) -> list[dict[str, Any]]:
    with connection_scope() as connection:
        rows = connection.execute(
            """
            SELECT id, token, platform, device_name, app_version, locale, created_at, updated_at,
                   last_seen_at, invalidated_at, invalidation_reason
            FROM notification_device_tokens
            WHERE user_id = ? AND invalidated_at IS NULL
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row)
        payload["is_active"] = True
        items.append(payload)
    return items


def invalidate_notification_device_tokens(*, token_ids: list[str], reason: str) -> None:
    if not token_ids:
        return
    now = _timestamp()
    with connection_scope() as connection:
        placeholders = ",".join("?" for _ in token_ids)
        connection.execute(
            f"""
            UPDATE notification_device_tokens
            SET invalidated_at = ?, invalidation_reason = ?, updated_at = ?
            WHERE id IN ({placeholders})
            """,
            (now, reason, now, *token_ids),
        )


def atomic_rate_limit_check(*, bucket_key: str, window_started_at: int, limit: int) -> bool:
    """Atomically check and increment the rate-limit counter.

    Returns True if the request is allowed, False if the limit is exceeded.
    Uses a single IMMEDIATE transaction so the read-check-write is atomic.
    """
    connection = get_connection()
    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            """
            INSERT INTO rate_limit_windows (bucket_key, window_started_at, request_count, updated_at)
            VALUES (?, ?, 0, ?)
            ON CONFLICT(bucket_key)
            DO UPDATE SET
                window_started_at = excluded.window_started_at,
                request_count = 0,
                updated_at = excluded.updated_at
            WHERE window_started_at != excluded.window_started_at
            """,
            (bucket_key, window_started_at, _timestamp()),
        )
        row = connection.execute(
            "SELECT request_count FROM rate_limit_windows WHERE bucket_key = ?",
            (bucket_key,),
        ).fetchone()
        current_count = int(row["request_count"])
        if current_count >= limit:
            connection.commit()
            return False
        connection.execute(
            "UPDATE rate_limit_windows SET request_count = request_count + 1, updated_at = ? WHERE bucket_key = ?",
            (_timestamp(), bucket_key),
        )
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
