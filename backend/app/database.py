from __future__ import annotations

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