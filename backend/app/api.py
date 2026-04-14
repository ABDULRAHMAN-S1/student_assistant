from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

try:
    from app.auth_service import AuthenticatedUser, authenticate_user, list_users, refresh_session, register_user, require_authenticated_user, require_role, update_user_role
    from app.chat import answer_question
    from app.config import get_settings
    from app.database import init_database, insert_feedback
    from app.logging_utils import configure_logging
    from app.rate_limit import RateLimiter
    from app.retrieve import (
        search,
    )
    from app.schemas import ChatRequest, FeedbackRequest, LoginRequest, RefreshRequest, RegisterRequest, SearchRequest, TranslateRequest, UpdateUserRoleRequest
    from app.translation_service import TranslationUnavailable, translate_text
except ImportError:
    from auth_service import AuthenticatedUser, authenticate_user, list_users, refresh_session, register_user, require_authenticated_user, require_role, update_user_role  # type: ignore
    from chat import answer_question  # type: ignore
    from config import get_settings  # type: ignore
    from database import init_database, insert_feedback  # type: ignore
    from logging_utils import configure_logging  # type: ignore
    from rate_limit import RateLimiter  # type: ignore
    from retrieve import (  # type: ignore
        search,
    )
    from schemas import ChatRequest, FeedbackRequest, LoginRequest, RefreshRequest, RegisterRequest, SearchRequest, TranslateRequest, UpdateUserRoleRequest  # type: ignore
    from translation_service import TranslationUnavailable, translate_text  # type: ignore


logger = logging.getLogger(__name__)
settings = get_settings()
configure_logging(settings.log_level)
init_database()
rate_limiter = RateLimiter()

RATE_LIMIT_RULES = {
    "/auth/login": (10, 60),
    "/auth/register": (5, 300),
    "/auth/refresh": (20, 60),
    "/chat": (20, 60),
    "/search": (40, 60),
    "/feedback": (20, 60),
    "/translate": (15, 60),
    "/public/health": (60, 60),
    "/health": (20, 60),
    "/users": (20, 60),
}


app = FastAPI(
    title=settings.api_title,
    description="Authenticated API for the Student Assistant application.",
    version=settings.api_version,
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Request-ID"],
)


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: object | None = None,
) -> JSONResponse:
    payload: dict[str, object] = {
        "error": {
            "code": code,
            "message": message,
        },
        "detail": message,
    }
    if details is not None:
        payload["error"] = {
            **payload["error"],
            "details": details,
        }
    return JSONResponse(status_code=status_code, content=payload)


def raise_api_error(*, status_code: int, code: str, message: str) -> None:
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


def trim_required_text(value: str, *, field_name: str) -> str:
    trimmed = (value or "").strip()
    if not trimmed:
        raise_api_error(status_code=422, code="validation_error", message=f"{field_name} must not be empty.")
    return trimmed


def client_identity(request: Request, user: AuthenticatedUser | None = None) -> str:
    if user is not None:
        return user.user_id
    if settings.trust_forwarded_for:
        client_host = request.client.host if request.client else ""
        if client_host and (not settings.trusted_proxy_ips or client_host in settings.trusted_proxy_ips):
            forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            if forwarded_for:
                return forwarded_for
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def serialize_current_user(current_user: AuthenticatedUser) -> dict[str, str]:
    return {
        "id": current_user.user_id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
    }


def enforce_rate_limit(request: Request, *, user: AuthenticatedUser | None = None) -> None:
    rule = RATE_LIMIT_RULES.get(request.url.path)
    if not rule:
        return
    limit, window_seconds = rule
    rate_limiter.enforce(
        route_key=request.url.path,
        actor_key=client_identity(request, user),
        limit=limit,
        window_seconds=window_seconds,
    )


@app.middleware("http")
async def apply_request_security(request: Request, call_next):
    request.state.request_id = request.headers.get("x-request-id", uuid4().hex)
    forwarded_proto = request.headers.get("x-forwarded-proto", "").lower().strip()
    effective_proto = forwarded_proto if settings.trust_forwarded_proto and forwarded_proto else request.url.scheme

    if settings.require_https and effective_proto != "https":
        return error_response(
            status_code=400,
            code="https_required",
            message="HTTPS is required for all API requests.",
        )

    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response


@app.exception_handler(RequestValidationError)
def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        status_code=422,
        code="validation_error",
        message="Request validation failed.",
        details=exc.errors(),
    )


@app.exception_handler(HTTPException)
def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code") or "request_error")
        message = str(detail.get("message") or "Request failed.")
        details = detail.get("details")
    else:
        code = "request_error"
        message = str(detail or "Request failed.")
        details = None
    return error_response(status_code=exc.status_code, code=code, message=message, details=details)


@app.exception_handler(Exception)
def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        "Unhandled API error",
        exc_info=exc,
        extra={"path": request.url.path, "request_id": getattr(request.state, "request_id", None)},
    )
    return error_response(
        status_code=500,
        code="internal_error",
        message="Internal server error.",
    )


@app.post("/auth/register")
def auth_register(http_request: Request, request: RegisterRequest) -> dict[str, object]:
    enforce_rate_limit(http_request)
    return register_user(email=request.email, password=request.password, full_name=request.full_name)


@app.post("/auth/login")
def auth_login(http_request: Request, request: LoginRequest) -> dict[str, object]:
    enforce_rate_limit(http_request)
    return authenticate_user(email=request.email, password=request.password)


@app.post("/auth/refresh")
def auth_refresh(http_request: Request, request: RefreshRequest) -> dict[str, object]:
    enforce_rate_limit(http_request)
    return refresh_session(request.refresh_token)


@app.get("/me")
def me(
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    return {"user": serialize_current_user(current_user)}


@app.get("/admin")
def admin_only(
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_role(["admin"])),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    return {
        "message": "Admin access granted.",
        "user": serialize_current_user(current_user),
    }


@app.get("/users")
def users_list(
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_role(["admin"])),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    return {
        "users": list_users(),
    }


@app.patch("/users/{user_id}/role")
def patch_user_role(
    user_id: str,
    request: UpdateUserRoleRequest,
    current_user: AuthenticatedUser = Depends(require_role(["admin"])),
) -> dict[str, object]:
    del current_user
    return {
        "user": update_user_role(user_id=user_id, role=request.role),
    }


@app.get("/health")
def health(http_request: Request, current_user: AuthenticatedUser = Depends(require_authenticated_user)) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    return {
        "status": "ok",
        "ready": True,
        "version": settings.api_version,
        "user": current_user.email,
        "role": current_user.role,
    }


@app.get("/public/health")
def public_health(http_request: Request) -> dict[str, object]:
    enforce_rate_limit(http_request)
    return {
        "status": "ok",
        "ready": True,
        "version": settings.api_version,
    }


@app.post("/chat")
def chat(
    http_request: Request,
    request: ChatRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    question = trim_required_text(request.question, field_name="question")
    try:
        return answer_question(question, top_k=request.top_k)
    except RuntimeError as exc:
        raise_api_error(status_code=400, code="bad_request", message=str(exc))


@app.post("/search")
def regulation_search(
    http_request: Request,
    request: SearchRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    query = trim_required_text(request.query, field_name="query")
    try:
        matches = search(query, top_k=request.top_k)
    except RuntimeError as exc:
        raise_api_error(status_code=400, code="bad_request", message=str(exc))

    results = [
        {
            "id": item["id"],
            "doc_type": item["metadata"].get("doc_type"),
            "document_title": item["metadata"].get("document_title"),
            "section": item["metadata"].get("section"),
            "article": item["metadata"].get("article"),
            "title": item["metadata"].get("title"),
            "score": item.get("score"),
            "content": item.get("content", ""),
            "content_preview": item.get("content", "")[:260].strip(),
        }
        for item in matches
    ]
    return {
        "query": query,
        "results": results,
    }


@app.post("/feedback")
def feedback(
    http_request: Request,
    request: FeedbackRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    question = trim_required_text(request.question, field_name="question")
    answer = trim_required_text(request.answer, field_name="answer")
    language = (request.language or "").strip()
    reason = (request.reason or "").strip()
    route_mode = (request.route_mode or "").strip()
    insert_feedback(
        feedback_id=uuid4().hex,
        user_id=current_user.user_id,
        question=question,
        answer=answer,
        helpful=request.helpful,
        language=language,
        sources=request.sources,
        reason=reason,
        route_mode=route_mode,
    )

    return {"status": "ok"}


@app.post("/translate")
def translate(
    http_request: Request,
    request: TranslateRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    text = trim_required_text(request.text, field_name="text")
    try:
        return translate_text(text)
    except TranslationUnavailable as exc:
        raise_api_error(status_code=503, code="translation_unavailable", message=str(exc))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=False)
