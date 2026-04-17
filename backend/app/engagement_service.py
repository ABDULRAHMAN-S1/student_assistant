from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import HTTPException

try:
    from app import database
except ImportError:
    import database  # type: ignore

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


def generate_notifications_for_user(*, user_id: str, limit: int = 25) -> int:
    profile = get_student_profile(user_id)
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
            },
        )
        if created:
            inserted += 1
    return inserted


def get_personalized_feed(*, user_id: str, include_read: bool, limit: int = 20) -> dict[str, object]:
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

    notifications = database.list_notifications(
        user_id=user_id,
        limit=limit,
        unread_only=not include_read,
    )
    unread_count = database.count_unread_notifications(user_id)
    return {
        "generated_count": 0,
        "unread_count": unread_count,
        "profile": profile,
        "notifications": notifications,
        "suggestions": suggestions,
    }


def mark_notification_as_read(*, user_id: str, notification_id: str) -> bool:
    return database.mark_notification_as_read(user_id=user_id, notification_id=notification_id)
