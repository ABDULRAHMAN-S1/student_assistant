from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


MAX_QUESTION_LENGTH = 500
MAX_SEARCH_QUERY_LENGTH = 500
MAX_ANSWER_LENGTH = 4000
MAX_LANGUAGE_LENGTH = 16
MAX_FEEDBACK_SOURCES = 10
MAX_REASON_LENGTH = 100
MAX_ROUTE_MODE_LENGTH = 50
MAX_MAJOR_LENGTH = 120
MAX_ACADEMIC_LEVEL_LENGTH = 80
MAX_TRACK_LENGTH = 120
MAX_INTEREST_LENGTH = 60
MAX_PROFILE_INTERESTS = 12
MAX_CONTENT_TITLE_LENGTH = 180
MAX_CONTENT_BODY_LENGTH = 2000
MAX_CONTENT_TYPE_LENGTH = 40
MAX_CONTENT_TAGS = 12
MAX_LINK_URL_LENGTH = 500
MAX_NOTIFICATION_CATEGORY_LENGTH = 80
MAX_NOTIFICATION_TOKEN_LENGTH = 4096
MAX_NOTIFICATION_PLATFORM_LENGTH = 32
MAX_NOTIFICATION_DEVICE_NAME_LENGTH = 120
MAX_NOTIFICATION_APP_VERSION_LENGTH = 40
MAX_NOTIFICATION_LOCALE_LENGTH = 16
MAX_NOTIFICATION_CURSOR_LENGTH = 512
MAX_NOTIFICATION_ROUTE_TYPE_LENGTH = 32
MAX_NOTIFICATION_CATEGORY_PREFERENCES = 32


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatRequest(StrictModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_LENGTH)
    top_k: int = Field(4, ge=1, le=10)


class SearchRequest(StrictModel):
    query: str = Field(..., min_length=1, max_length=MAX_SEARCH_QUERY_LENGTH)
    top_k: int = Field(5, ge=1, le=10)


class FeedbackRequest(StrictModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_LENGTH)
    answer: str = Field(..., min_length=1, max_length=MAX_ANSWER_LENGTH)
    helpful: bool
    language: str = Field("", max_length=MAX_LANGUAGE_LENGTH)
    sources: list[dict[str, object]] = Field(default_factory=list, max_length=MAX_FEEDBACK_SOURCES)
    reason: str = Field("", max_length=MAX_REASON_LENGTH)
    route_mode: str = Field("", max_length=MAX_ROUTE_MODE_LENGTH)


class TranslateRequest(StrictModel):
    text: str = Field(..., min_length=1, max_length=MAX_ANSWER_LENGTH)


class RegisterRequest(StrictModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=10, max_length=256)
    full_name: str = Field(..., min_length=1, max_length=200)


class LoginRequest(StrictModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=10, max_length=256)


class RefreshRequest(StrictModel):
    refresh_token: str = Field(..., min_length=32, max_length=4096)


class UpdateUserRoleRequest(StrictModel):
    role: str = Field(..., min_length=1, max_length=32)


class StudentProfileUpdateRequest(StrictModel):
    major: str = Field("", max_length=MAX_MAJOR_LENGTH)
    academic_level: str = Field("", max_length=MAX_ACADEMIC_LEVEL_LENGTH)
    track: str = Field("", max_length=MAX_TRACK_LENGTH)
    interests: list[str] = Field(default_factory=list, max_length=MAX_PROFILE_INTERESTS)


class LiveContentCreateRequest(StrictModel):
    content_type: str = Field(..., min_length=1, max_length=MAX_CONTENT_TYPE_LENGTH)
    title: str = Field(..., min_length=1, max_length=MAX_CONTENT_TITLE_LENGTH)
    body: str = Field(..., min_length=1, max_length=MAX_CONTENT_BODY_LENGTH)
    link_url: str = Field("", max_length=MAX_LINK_URL_LENGTH)
    target_major: str = Field("", max_length=MAX_MAJOR_LENGTH)
    target_level: str = Field("", max_length=MAX_ACADEMIC_LEVEL_LENGTH)
    tags: list[str] = Field(default_factory=list, max_length=MAX_CONTENT_TAGS)
    priority: int = Field(0, ge=0, le=10)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


NotificationRouteType = Literal[
    "course",
    "event",
    "review",
    "chat",
    "search",
    "external_url",
    "engagement",
]


class NotificationRoute(StrictModel):
    type: NotificationRouteType
    payload: dict[str, Any] = Field(default_factory=dict)


class NotificationMetadataResponse(StrictModel):
    content_type: str | None = None
    match_reasons: list[str] = Field(default_factory=list)
    link_url: str | None = None
    route: NotificationRoute | None = None


class NotificationItemResponse(StrictModel):
    id: str
    category: str
    title: str
    message: str
    is_read: bool
    priority: int
    created_at: str
    read_at: str | None = None
    metadata: NotificationMetadataResponse


class NotificationFeedPageResponse(StrictModel):
    has_more: bool = False
    next_cursor: str | None = None


class StudentProfileResponse(StrictModel):
    user_id: str
    major: str
    academic_level: str
    track: str
    interests: list[str] = Field(default_factory=list)
    updated_at: str | None = None


class SuggestionItemResponse(StrictModel):
    id: str
    content_type: str
    title: str
    body_preview: str
    link_url: str = ""
    priority: int = 0
    match_score: int = 0
    match_reasons: list[str] = Field(default_factory=list)
    starts_at: str | None = None
    ends_at: str | None = None


class EngagementFeedResponse(StrictModel):
    generated_count: int = 0
    unread_count: int = 0
    profile: StudentProfileResponse
    notifications: list[NotificationItemResponse] = Field(default_factory=list)
    suggestions: list[SuggestionItemResponse] = Field(default_factory=list)
    page: NotificationFeedPageResponse = Field(default_factory=NotificationFeedPageResponse)


class NotificationCategoryPreference(StrictModel):
    category: str = Field(..., min_length=1, max_length=MAX_NOTIFICATION_CATEGORY_LENGTH)
    enable_push: bool = True
    enable_in_app: bool = True
    muted: bool = False


class NotificationCategoryPreferenceUpdate(StrictModel):
    category: str = Field(..., min_length=1, max_length=MAX_NOTIFICATION_CATEGORY_LENGTH)
    enable_push: bool | None = None
    enable_in_app: bool | None = None
    muted: bool | None = None


class NotificationPreferencesResponse(StrictModel):
    enable_push: bool = True
    enable_in_app: bool = True
    categories: list[NotificationCategoryPreference] = Field(default_factory=list)
    updated_at: str | None = None


class NotificationPreferencesUpdateRequest(StrictModel):
    enable_push: bool | None = None
    enable_in_app: bool | None = None
    categories: list[NotificationCategoryPreferenceUpdate] = Field(
        default_factory=list,
        max_length=MAX_NOTIFICATION_CATEGORY_PREFERENCES,
    )


class DeviceTokenRegisterRequest(StrictModel):
    token: str = Field(..., min_length=32, max_length=MAX_NOTIFICATION_TOKEN_LENGTH)
    platform: str = Field(..., min_length=2, max_length=MAX_NOTIFICATION_PLATFORM_LENGTH)
    device_name: str = Field("", max_length=MAX_NOTIFICATION_DEVICE_NAME_LENGTH)
    app_version: str = Field("", max_length=MAX_NOTIFICATION_APP_VERSION_LENGTH)
    locale: str = Field("", max_length=MAX_NOTIFICATION_LOCALE_LENGTH)


class DeviceTokenResponse(StrictModel):
    id: str
    platform: str
    device_name: str = ""
    app_version: str = ""
    locale: str = ""
    is_active: bool = True
    created_at: str
    updated_at: str
    last_seen_at: str
    invalidated_at: str | None = None
    invalidation_reason: str | None = None


class DeviceTokenEnvelopeResponse(StrictModel):
    token: DeviceTokenResponse


class NotificationReadResponse(StrictModel):
    status: str = "ok"
    notification: NotificationItemResponse
    unread_count: int


class NotificationGenerateResponse(StrictModel):
    status: str = "ok"
    generated_count: int = 0