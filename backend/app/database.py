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


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


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
    now = _timestamp()
    with connection_scope() as connection:
        connection.execute(
            "UPDATE users SET role = ?, updated_at = ? WHERE id = ?",
            (role, now, user_id),
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