from __future__ import annotations

from datetime import datetime

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