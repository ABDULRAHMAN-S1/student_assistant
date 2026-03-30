from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


MAX_QUESTION_LENGTH = 500
MAX_SEARCH_QUERY_LENGTH = 500
MAX_ANSWER_LENGTH = 4000
MAX_LANGUAGE_LENGTH = 16
MAX_FEEDBACK_SOURCES = 10


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