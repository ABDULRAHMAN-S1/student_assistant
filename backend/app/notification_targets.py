from __future__ import annotations

from typing import Any, Literal

try:
    from app.schemas import NotificationRoute
except ImportError:
    from schemas import NotificationRoute  # type: ignore

NotificationRouteType = Literal[
    "course",
    "event",
    "review",
    "chat",
    "search",
    "external_url",
    "engagement",
]

_ROUTE_TYPES: frozenset[str] = frozenset(
    {
        "course",
        "event",
        "review",
        "chat",
        "search",
        "external_url",
        "engagement",
    }
)


def make_notification_route(*, route_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized_type = (route_type or "").strip().lower()
    if normalized_type not in _ROUTE_TYPES:
        raise ValueError(f"Unsupported notification route type: {route_type}")
    cleaned_payload = dict(payload or {})
    return NotificationRoute(type=normalized_type, payload=cleaned_payload).model_dump()


def validate_notification_route(route: dict[str, Any] | None) -> dict[str, Any]:
    model = NotificationRoute.model_validate(route or {"type": "engagement", "payload": {}})
    return model.model_dump()


def route_for_live_content(item: dict[str, object]) -> dict[str, Any]:
    link_url = str(item.get("link_url") or "").strip()
    content_type = str(item.get("content_type") or "").strip().lower()
    payload: dict[str, Any] = {
        "content_item_id": str(item.get("id") or ""),
        "content_type": content_type,
    }
    if link_url:
        payload["url"] = link_url
        return make_notification_route(route_type="external_url", payload=payload)
    if content_type == "event":
        return make_notification_route(route_type="event", payload=payload)
    return make_notification_route(route_type="engagement", payload=payload)
