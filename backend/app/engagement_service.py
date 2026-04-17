from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import HTTPException

try:
    from app import database
    from app.notification_delivery import DeliverySummary, get_notification_delivery_service
    from app.notification_targets import route_for_live_content, validate_notification_route
    from app.schemas import (
        DeviceTokenResponse,
        EngagementFeedResponse,
        NotificationCategoryPreference,
        NotificationItemResponse,
        NotificationPreferencesResponse,
        NotificationReadResponse,
        NotificationRoute,
        StudentProfileResponse,
        SuggestionItemResponse,
    )
except ImportError:
    import database  # type: ignore
    from notification_delivery import DeliverySummary, get_notification_delivery_service  # type: ignore
    from notification_targets import route_for_live_content, validate_notification_route  # type: ignore
    from schemas import (  # type: ignore
        DeviceTokenResponse,
        EngagementFeedResponse,
        NotificationCategoryPreference,
        NotificationItemResponse,
        NotificationPreferencesResponse,
        NotificationReadResponse,
        NotificationRoute,
        StudentProfileResponse,
        SuggestionItemResponse,
    )

ALLOWED_CONTENT_TYPES = frozenset({"event", "academic_tip", "opportunity", "deadline"})
MAX_NOTIFICATION_MESSAGE_LENGTH = 260


def _clean_text(value: str) -> str:
    return " ".join((value or "").strip().split())


def _normalize_tags(values: list[str], *, limit: int = 12) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        cleaned = _clean_text(raw).lower()
        if not cleaned or cleaned in seen:
            continue
        normalized.append(cleaned)
        seen.add(cleaned)
        if len(normalized) >= limit:
            break
    return normalized


def _ensure_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _normalized_category(category: str) -> str:
    cleaned = _clean_text(category).lower()
    if not cleaned:
        raise HTTPException(
            status_code=422,
            detail={"code": "validation_error", "message": "Notification category must not be empty."},
        )
    return cleaned


def _normalize_category_preferences(categories: list[dict[str, object]]) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    seen: set[str] = set()
    for category in categories:
        normalized_category = _normalized_category(str(category.get("category") or ""))
        if normalized_category in seen:
            continue
        normalized.append(
            {
                "category": normalized_category,
                "enable_push": bool(category.get("enable_push", True)),
                "enable_in_app": bool(category.get("enable_in_app", True)),
                "muted": bool(category.get("muted", False)),
            }
        )
        seen.add(normalized_category)
    normalized.sort(key=lambda item: str(item["category"]))
    return normalized


def _category_settings(preferences: dict[str, object], category: str) -> dict[str, bool]:
    normalized_category = _normalized_category(category)
    category_settings = {
        "enable_push": bool(preferences.get("enable_push", True)),
        "enable_in_app": bool(preferences.get("enable_in_app", True)),
        "muted": False,
    }
    for item in list(preferences.get("categories") or []):
        if _normalized_category(str(item.get("category") or "")) != normalized_category:
            continue
        if "enable_push" in item:
            category_settings["enable_push"] = bool(item.get("enable_push"))
        if "enable_in_app" in item:
            category_settings["enable_in_app"] = bool(item.get("enable_in_app"))
        if "muted" in item:
            category_settings["muted"] = bool(item.get("muted"))
        break
    return category_settings


def _serialize_profile(profile: dict[str, object]) -> dict[str, object]:
    return StudentProfileResponse.model_validate(profile).model_dump()


def _serialize_suggestion(suggestion: dict[str, object]) -> dict[str, object]:
    return SuggestionItemResponse.model_validate(suggestion).model_dump()


def _serialize_notification(notification: dict[str, object]) -> dict[str, object]:
    metadata = dict(notification.get("metadata") or {})
    route = validate_notification_route(metadata.get("route") if isinstance(metadata, dict) else None)
    metadata["route"] = NotificationRoute.model_validate(route).model_dump()
    payload = {
        "id": notification.get("id"),
        "category": notification.get("category"),
        "title": notification.get("title"),
        "message": notification.get("message"),
        "is_read": notification.get("is_read"),
        "priority": notification.get("priority"),
        "created_at": notification.get("created_at"),
        "read_at": notification.get("read_at"),
        "metadata": metadata,
    }
    return NotificationItemResponse.model_validate(payload).model_dump()


def get_student_profile(user_id: str) -> dict[str, object]:
    return database.fetch_student_profile(user_id)


def update_student_profile(
    *,
    user_id: str,
    major: str,
    academic_level: str,
    track: str,
    interests: list[str],
) -> dict[str, object]:
    cleaned_major = _clean_text(major)
    cleaned_level = _clean_text(academic_level)
    cleaned_track = _clean_text(track)
    cleaned_interests = _normalize_tags(interests)
    return database.upsert_student_profile(
        user_id=user_id,
        major=cleaned_major,
        academic_level=cleaned_level,
        track=cleaned_track,
        interests=cleaned_interests,
    )


def create_live_content(
    *,
    created_by: str,
    content_type: str,
    title: str,
    body: str,
    link_url: str,
    target_major: str,
    target_level: str,
    tags: list[str],
    priority: int,
    starts_at: datetime | None,
    ends_at: datetime | None,
) -> dict[str, object]:
    normalized_content_type = _clean_text(content_type).lower()
    if normalized_content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": "content_type must be one of: event, academic_tip, opportunity, deadline.",
            },
        )
    starts_at_iso = _ensure_iso(starts_at)
    ends_at_iso = _ensure_iso(ends_at)
    if starts_at_iso and ends_at_iso and starts_at_iso > ends_at_iso:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_error",
                "message": "starts_at must be earlier than or equal to ends_at.",
            },
        )
    return database.insert_live_content_item(
        item_id=uuid4().hex,
        content_type=normalized_content_type,
        title=_clean_text(title),
        body=_clean_text(body),
        link_url=_clean_text(link_url),
        target_major=_clean_text(target_major).lower(),
        target_level=_clean_text(target_level).lower(),
        tags=_normalize_tags(tags),
        priority=priority,
        starts_at=starts_at_iso,
        ends_at=ends_at_iso,
        created_by=created_by,
    )


def _score_item(*, item: dict[str, object], profile: dict[str, object]) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = int(item.get("priority") or 0)
    profile_major = _clean_text(str(profile.get("major") or "")).lower()
    profile_level = _clean_text(str(profile.get("academic_level") or "")).lower()
    profile_interests = set(_normalize_tags(list(profile.get("interests") or []), limit=50))

    target_major = _clean_text(str(item.get("target_major") or "")).lower()
    target_level = _clean_text(str(item.get("target_level") or "")).lower()
    item_tags = set(_normalize_tags(list(item.get("tags") or []), limit=50))

    if target_major:
        if target_major != profile_major:
            return -1, []
        score += 3
        reasons.append("major_match")
    if target_level:
        if target_level != profile_level:
            return -1, []
        score += 2
        reasons.append("level_match")

    common_tags = sorted(profile_interests.intersection(item_tags))
    if common_tags:
        score += min(3, len(common_tags))
        reasons.append("interest_match")
    return score, reasons


def get_notification_preferences(*, user_id: str) -> dict[str, object]:
    stored = database.fetch_notification_preferences(user_id)
    payload = {
        "enable_push": bool(stored.get("enable_push", True)),
        "enable_in_app": bool(stored.get("enable_in_app", True)),
        "categories": _normalize_category_preferences(list(stored.get("categories") or [])),
        "updated_at": stored.get("updated_at"),
    }
    return NotificationPreferencesResponse.model_validate(payload).model_dump()


def update_notification_preferences(
    *,
    user_id: str,
    enable_push: bool | None,
    enable_in_app: bool | None,
    categories: list[dict[str, object]],
) -> dict[str, object]:
    current = get_notification_preferences(user_id=user_id)
    by_category = {
        str(item["category"]): dict(item)
        for item in list(current.get("categories") or [])
    }
    for category in categories:
        normalized_category = _normalized_category(str(category.get("category") or ""))
        merged = dict(by_category.get(normalized_category) or {"category": normalized_category})
        for key in ("enable_push", "enable_in_app", "muted"):
            if category.get(key) is not None:
                merged[key] = bool(category.get(key))
        by_category[normalized_category] = merged
    stored = database.upsert_notification_preferences(
        user_id=user_id,
        enable_push=bool(current["enable_push"] if enable_push is None else enable_push),
        enable_in_app=bool(current["enable_in_app"] if enable_in_app is None else enable_in_app),
        categories=_normalize_category_preferences(list(by_category.values())),
    )
    return get_notification_preferences(user_id=str(stored["user_id"]))


def register_device_token(
    *,
    user_id: str,
    token: str,
    platform: str,
    device_name: str,
    app_version: str,
    locale: str,
) -> dict[str, object]:
    created = database.upsert_notification_device_token(
        token_id=uuid4().hex,
        user_id=user_id,
        token=_clean_text(token),
        platform=_clean_text(platform).lower(),
        device_name=_clean_text(device_name),
        app_version=_clean_text(app_version),
        locale=_clean_text(locale).lower(),
    )
    return DeviceTokenResponse.model_validate(created).model_dump()


def delete_device_token(*, user_id: str, token_id: str) -> bool:
    return database.delete_notification_device_token(user_id=user_id, token_id=token_id)


def _deliver_push_if_needed(
    *,
    user_id: str,
    notification_id: str,
    title: str,
    message: str,
    category: str,
    route: dict[str, object],
) -> DeliverySummary | None:
    preferences = get_notification_preferences(user_id=user_id)
    category_settings = _category_settings(preferences, category)
    if not category_settings["enable_push"] or category_settings["muted"]:
        database.update_notification_delivery(
            notification_id=notification_id,
            user_id=user_id,
            push_status="disabled",
            last_delivery_error="push_disabled_by_preference",
        )
        return None
    delivery_service = get_notification_delivery_service()
    tokens = database.list_active_notification_device_tokens(user_id)
    summary = delivery_service.send_notification(
        device_tokens=tokens,
        title=title,
        body=message,
        data={
            "notification_id": notification_id,
            "category": category,
            "route": json.dumps(route, ensure_ascii=False),
            "route_type": str(route.get("type") or "engagement"),
        },
    )
    if summary.invalidated_token_ids:
        database.invalidate_notification_device_tokens(
            token_ids=list(summary.invalidated_token_ids),
            reason="provider_rejected_token",
        )
    status = "delivered" if summary.delivered_count > 0 else "failed"
    database.update_notification_delivery(
        notification_id=notification_id,
        user_id=user_id,
        push_status=status,
        delivered_at=datetime.now(timezone.utc).isoformat() if summary.delivered_count > 0 else None,
        last_delivery_error="; ".join(
            filter(None, [attempt.error_code or attempt.error_message for attempt in summary.failures if not attempt.success])
        )[:500]
        or None,
    )
    return summary


def generate_notifications_for_user(*, user_id: str, limit: int = 25) -> int:
    profile = get_student_profile(user_id)
    preferences = get_notification_preferences(user_id=user_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    active_items = database.list_active_live_content(now_iso=now_iso, limit=200)
    ranked_items: list[tuple[int, dict[str, object], list[str]]] = []
    for item in active_items:
        score, reasons = _score_item(item=item, profile=profile)
        if score < 0:
            continue
        ranked_items.append((score, item, reasons))
    ranked_items.sort(key=lambda pair: (pair[0], str(pair[1].get("created_at") or "")), reverse=True)

    inserted = 0
    for score, item, reasons in ranked_items[:limit]:
        category = f"live_{item['content_type']}"
        category_settings = _category_settings(preferences, category)
        if not category_settings["enable_in_app"] or category_settings["muted"]:
            continue
        route = route_for_live_content(item)
        notification_id = str(uuid5(NAMESPACE_URL, f"{user_id}:{item['id']}:{category}"))
        created = database.insert_notification(
            notification_id=notification_id,
            user_id=user_id,
            category=category,
            title=str(item["title"]),
            message=str(item["body"])[:MAX_NOTIFICATION_MESSAGE_LENGTH],
            content_item_id=str(item["id"]),
            priority=score,
            metadata={
                "content_type": item["content_type"],
                "match_reasons": reasons,
                "link_url": item.get("link_url") or "",
                "route": route,
            },
            route_type=str(route["type"]),
            route_payload=dict(route.get("payload") or {}),
        )
        if not created:
            continue
        inserted += 1
        _deliver_push_if_needed(
            user_id=user_id,
            notification_id=notification_id,
            title=str(item["title"]),
            message=str(item["body"])[:MAX_NOTIFICATION_MESSAGE_LENGTH],
            category=category,
            route=route,
        )
    return inserted


def get_personalized_feed(
    *,
    user_id: str,
    include_read: bool,
    limit: int = 20,
    cursor: str | None = None,
) -> dict[str, object]:
    profile = get_student_profile(user_id)
    now_iso = datetime.now(timezone.utc).isoformat()
    active_items = database.list_active_live_content(now_iso=now_iso, limit=30)

    suggestions: list[dict[str, object]] = []
    ranked_items: list[tuple[int, dict[str, object], list[str]]] = []
    for item in active_items:
        score, reasons = _score_item(item=item, profile=profile)
        if score < 0:
            continue
        ranked_items.append((score, item, reasons))
    ranked_items.sort(key=lambda pair: (pair[0], str(pair[1].get("created_at") or "")), reverse=True)

    for score, item, reasons in ranked_items[:10]:
        suggestions.append(
            _serialize_suggestion(
                {
                    "id": item["id"],
                    "content_type": item["content_type"],
                    "title": item["title"],
                    "body_preview": str(item["body"])[:180],
                    "link_url": item.get("link_url") or "",
                    "priority": item.get("priority", 0),
                    "match_score": score,
                    "match_reasons": reasons,
                    "starts_at": item.get("starts_at"),
                    "ends_at": item.get("ends_at"),
                }
            )
        )

    try:
        notifications_page = database.list_notifications(
            user_id=user_id,
            limit=limit,
            unread_only=not include_read,
            cursor=cursor,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "validation_error", "message": f"Invalid pagination cursor: {exc}"},
        ) from exc
    unread_count = database.count_unread_notifications(user_id)
    response = EngagementFeedResponse.model_validate(
        {
            "generated_count": 0,
            "unread_count": unread_count,
            "profile": _serialize_profile(profile),
            "notifications": [_serialize_notification(item) for item in notifications_page["items"]],
            "suggestions": suggestions,
            "page": {
                "has_more": bool(notifications_page["has_more"]),
                "next_cursor": notifications_page["next_cursor"],
            },
        }
    )
    return response.model_dump()


def mark_notification_as_read(*, user_id: str, notification_id: str) -> dict[str, object] | None:
    database.mark_notification_as_read(user_id=user_id, notification_id=notification_id)
    updated = database.fetch_notification(notification_id, user_id=user_id)
    if updated is None:
        return None
    return NotificationReadResponse.model_validate(
        {
            "status": "ok",
            "notification": _serialize_notification(updated),
            "unread_count": database.count_unread_notifications(user_id),
        }
    ).model_dump()
