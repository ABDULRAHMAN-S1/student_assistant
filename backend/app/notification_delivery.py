from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

try:
    from firebase_admin import credentials, initialize_app, messaging
    from firebase_admin import exceptions as firebase_exceptions
except ImportError:  # pragma: no cover - optional dependency in tests
    credentials = None  # type: ignore[assignment]
    initialize_app = None  # type: ignore[assignment]
    messaging = None  # type: ignore[assignment]
    firebase_exceptions = None  # type: ignore[assignment]

try:
    from app.config import get_settings
except ImportError:
    from config import get_settings  # type: ignore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeliveryAttempt:
    token_id: str
    success: bool
    error_code: str | None = None
    error_message: str | None = None
    token_invalid: bool = False


@dataclass(frozen=True)
class DeliverySummary:
    attempted_count: int
    delivered_count: int
    failed_count: int
    invalidated_token_ids: tuple[str, ...]
    failures: tuple[DeliveryAttempt, ...]


class NotificationDeliveryService:
    def __init__(self) -> None:
        self._settings = get_settings()

    @property
    def is_enabled(self) -> bool:
        return bool(self._settings.notifications_push_enabled and self._settings.fcm_service_account_json)

    def send_notification(
        self,
        *,
        device_tokens: list[dict[str, Any]],
        title: str,
        body: str,
        data: dict[str, str],
    ) -> DeliverySummary:
        active_tokens = [
            token for token in device_tokens if not token.get("invalidated_at") and str(token.get("token") or "").strip()
        ]
        if not active_tokens:
            return DeliverySummary(
                attempted_count=0,
                delivered_count=0,
                failed_count=0,
                invalidated_token_ids=(),
                failures=(),
            )

        if not self.is_enabled:
            failures = tuple(
                DeliveryAttempt(
                    token_id=str(token["id"]),
                    success=False,
                    error_code="push_not_configured",
                    error_message="Push delivery is not configured.",
                    token_invalid=False,
                )
                for token in active_tokens
            )
            return DeliverySummary(
                attempted_count=len(active_tokens),
                delivered_count=0,
                failed_count=len(active_tokens),
                invalidated_token_ids=(),
                failures=failures,
            )

        app = _get_firebase_app(self._settings.fcm_service_account_json)
        attempts: list[DeliveryAttempt] = []

        for token in active_tokens:
            token_value = str(token["token"])
            try:
                message = messaging.Message(  # type: ignore[union-attr]
                    token=token_value,
                    notification=messaging.Notification(title=title, body=body),  # type: ignore[union-attr]
                    data=data,
                )
                messaging.send(message, app=app)  # type: ignore[union-attr]
                attempts.append(
                    DeliveryAttempt(
                        token_id=str(token["id"]),
                        success=True,
                    )
                )
            except Exception as exc:  # pragma: no cover - exercised with mocks in tests
                error_code = _error_code(exc)
                token_invalid = error_code in {
                    "registration-token-not-registered",
                    "invalid-registration-token",
                    "unregistered",
                }
                attempts.append(
                    DeliveryAttempt(
                        token_id=str(token["id"]),
                        success=False,
                        error_code=error_code,
                        error_message=str(exc),
                        token_invalid=token_invalid,
                    )
                )

        invalidated_ids = tuple(attempt.token_id for attempt in attempts if attempt.token_invalid)
        delivered_count = sum(1 for attempt in attempts if attempt.success)
        return DeliverySummary(
            attempted_count=len(attempts),
            delivered_count=delivered_count,
            failed_count=len(attempts) - delivered_count,
            invalidated_token_ids=invalidated_ids,
            failures=tuple(attempts),
        )


@lru_cache(maxsize=1)
def get_notification_delivery_service() -> NotificationDeliveryService:
    return NotificationDeliveryService()


@lru_cache(maxsize=1)
def _get_firebase_app(service_account_json: str):
    if initialize_app is None or credentials is None:
        raise RuntimeError("firebase-admin is not installed.")
    try:
        payload = json.loads(service_account_json)
    except json.JSONDecodeError as exc:
        raise RuntimeError("FCM_SERVICE_ACCOUNT_JSON must be valid JSON.") from exc
    credential = credentials.Certificate(payload)
    return initialize_app(credential, name="student-assistant-notifications")


def _error_code(exc: Exception) -> str:
    if firebase_exceptions is not None and isinstance(exc, firebase_exceptions.FirebaseError):
        return str(getattr(exc, "code", "") or "firebase_error")
    text = str(exc).strip().lower()
    if "registration-token-not-registered" in text:
        return "registration-token-not-registered"
    if "invalid registration token" in text or "invalid-registration-token" in text:
        return "invalid-registration-token"
    return "delivery_failed"
