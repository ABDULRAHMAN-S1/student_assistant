from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

try:
    from app.admin_dashboard import render_admin_dashboard, render_admin_login
    from app.admin_service import (
        create_admin_user,
        create_role,
        get_activity_logs,
        get_admin_user,
        get_dashboard_summary,
        get_permission_catalog,
        list_admin_users,
        list_roles,
        update_admin_user,
        update_role,
        update_user_permissions,
    )
    from app.auth_service import (
        AuthenticatedUser,
        authenticate_user,
        list_users,
        refresh_session,
        register_user,
        require_admin_access_token,
        require_admin_permission,
        require_authenticated_user,
        require_permission,
    )
    from app.config import get_settings
    from app.database import init_database, insert_feedback
    from app.engagement_service import (
        create_live_content,
        delete_device_token,
        generate_notifications_for_user,
        get_notification_preferences,
        get_personalized_feed,
        get_student_profile,
        mark_notification_as_read,
        register_device_token,
        update_notification_preferences,
        update_student_profile,
    )
    from app.logging_utils import configure_logging
    from app.rate_limit import RateLimiter
    from app.schemas import (
        ActivityLogResponse,
        AdminUserCreateRequest,
        AdminUserResponse,
        AdminUserUpdateRequest,
        ChatRequest,
        DeviceTokenEnvelopeResponse,
        DeviceTokenRegisterRequest,
        FeedbackRequest,
        LiveContentCreateRequest,
        LoginRequest,
        NotificationGenerateResponse,
        NotificationPreferencesResponse,
        NotificationPreferencesUpdateRequest,
        NotificationReadResponse,
        PermissionDefinitionResponse,
        RefreshRequest,
        RegisterRequest,
        RoleCreateRequest,
        RoleResponse,
        RoleUpdateRequest,
        SearchRequest,
        StudentProfileUpdateRequest,
        TranslateRequest,
        UpdateUserRoleRequest,
        UserPermissionOverrideUpdateRequest,
    )
    from app.translation_service import TranslationUnavailable, translate_text
except ImportError:
    from admin_dashboard import render_admin_dashboard, render_admin_login  # type: ignore
    from admin_service import create_admin_user, create_role, get_activity_logs, get_admin_user, get_dashboard_summary, get_permission_catalog, list_admin_users, list_roles, update_admin_user, update_role, update_user_permissions  # type: ignore
    from auth_service import AuthenticatedUser, authenticate_user, list_users, refresh_session, register_user, require_admin_access_token, require_admin_permission, require_authenticated_user, require_permission  # type: ignore
    from config import get_settings  # type: ignore
    from database import init_database, insert_feedback  # type: ignore
    from engagement_service import (  # type: ignore
        create_live_content,
        delete_device_token,
        generate_notifications_for_user,
        get_notification_preferences,
        get_personalized_feed,
        get_student_profile,
        mark_notification_as_read,
        register_device_token,
        update_notification_preferences,
        update_student_profile,
    )
    from logging_utils import configure_logging  # type: ignore
    from rate_limit import RateLimiter  # type: ignore
    from schemas import (  # type: ignore
        ActivityLogResponse,
        AdminUserCreateRequest,
        AdminUserResponse,
        AdminUserUpdateRequest,
        ChatRequest,
        DeviceTokenEnvelopeResponse,
        DeviceTokenRegisterRequest,
        FeedbackRequest,
        LiveContentCreateRequest,
        LoginRequest,
        NotificationGenerateResponse,
        NotificationPreferencesResponse,
        NotificationPreferencesUpdateRequest,
        NotificationReadResponse,
        PermissionDefinitionResponse,
        RefreshRequest,
        RegisterRequest,
        RoleCreateRequest,
        RoleResponse,
        RoleUpdateRequest,
        SearchRequest,
        StudentProfileUpdateRequest,
        TranslateRequest,
        UpdateUserRoleRequest,
        UserPermissionOverrideUpdateRequest,
    )
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
    "/admin/summary": (20, 60),
    "/admin/dashboard": (20, 60),
    "/admin/users": (20, 60),
    "/admin/roles": (20, 60),
    "/admin/permissions": (20, 60),
    "/admin/activity-logs": (20, 60),
    "/engagement/profile": (30, 60),
    "/engagement/feed": (20, 60),
    "/engagement/content": (20, 60),
    "/engagement/notifications/generate": (10, 60),
    "/engagement/notifications/preferences": (20, 60),
    "/engagement/device-tokens": (20, 60),
    "/engagement/notifications/read": (30, 60),
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
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
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
        # Only trust X-Forwarded-For when the direct client is a known proxy.
        if client_host and settings.trusted_proxy_ips and client_host in settings.trusted_proxy_ips:
            forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            if forwarded_for:
                return forwarded_for
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def serialize_current_user(current_user: AuthenticatedUser) -> dict[str, object]:
    return {
        "id": current_user.user_id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "permissions": list(current_user.permissions),
    }


def enforce_rate_limit(request: Request, *, user: AuthenticatedUser | None = None) -> None:
    path = request.url.path
    rule = RATE_LIMIT_RULES.get(path)
    if rule is None and path.startswith("/engagement/notifications/") and path.endswith("/read"):
        rule = RATE_LIMIT_RULES.get("/engagement/notifications/read")
    if rule is None and path.startswith("/engagement/device-tokens/"):
        rule = RATE_LIMIT_RULES.get("/engagement/device-tokens")
    if rule is None and path.startswith("/admin/users/"):
        rule = RATE_LIMIT_RULES.get("/admin/users")
    if rule is None and path.startswith("/admin/roles/"):
        rule = RATE_LIMIT_RULES.get("/admin/roles")
    if rule is None and path.startswith("/users/") and path.endswith("/role"):
        rule = RATE_LIMIT_RULES.get("/users")
    if not rule:
        return
    limit, window_seconds = rule
    rate_limiter.enforce(
        route_key=path,
        actor_key=client_identity(request, user),
        limit=limit,
        window_seconds=window_seconds,
    )


@app.middleware("http")
async def apply_request_security(request: Request, call_next):
    request.state.request_id = request.headers.get("x-request-id", uuid4().hex)
    forwarded_proto = request.headers.get("x-forwarded-proto", "").lower().strip()
    direct_client = request.client.host if request.client else ""
    is_trusted_proxy = bool(direct_client and settings.trusted_proxy_ips and direct_client in settings.trusted_proxy_ips)
    effective_proto = (
        forwarded_proto
        if settings.trust_forwarded_proto and forwarded_proto and is_trusted_proxy
        else request.url.scheme
    )

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


@app.get("/engagement/profile")
def get_profile(
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    return {
        "profile": get_student_profile(current_user.user_id),
    }


@app.put("/engagement/profile")
def put_profile(
    http_request: Request,
    request: StudentProfileUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    profile = update_student_profile(
        user_id=current_user.user_id,
        major=request.major,
        academic_level=request.academic_level,
        track=request.track,
        interests=request.interests,
    )
    return {"profile": profile}


@app.post("/engagement/content")
def post_live_content(
    http_request: Request,
    request: LiveContentCreateRequest,
    current_user: AuthenticatedUser = Depends(require_permission("engagement.manage")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    item = create_live_content(
        created_by=current_user.user_id,
        content_type=request.content_type,
        title=request.title,
        body=request.body,
        link_url=request.link_url,
        target_major=request.target_major,
        target_level=request.target_level,
        tags=request.tags,
        priority=request.priority,
        starts_at=request.starts_at,
        ends_at=request.ends_at,
    )
    return {"item": item}


@app.get("/engagement/feed")
def get_feed(
    http_request: Request,
    include_read: bool = False,
    limit: int = 20,
    cursor: str | None = None,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    bounded_limit = max(1, min(limit, 50))
    return get_personalized_feed(
        user_id=current_user.user_id,
        include_read=include_read,
        limit=bounded_limit,
        cursor=cursor,
    )


@app.post("/engagement/notifications/generate")
def post_generate_notifications(
    http_request: Request,
    limit: int = 20,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    bounded_limit = max(1, min(limit, 100))
    generated_count = generate_notifications_for_user(
        user_id=current_user.user_id,
        limit=bounded_limit,
    )
    return NotificationGenerateResponse(generated_count=generated_count).model_dump()


@app.get("/engagement/notifications/preferences")
def get_notification_preferences_endpoint(
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    return NotificationPreferencesResponse.model_validate(
        get_notification_preferences(user_id=current_user.user_id)
    ).model_dump()


@app.put("/engagement/notifications/preferences")
def put_notification_preferences(
    http_request: Request,
    request: NotificationPreferencesUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    return NotificationPreferencesResponse.model_validate(
        update_notification_preferences(
            user_id=current_user.user_id,
            enable_push=request.enable_push,
            enable_in_app=request.enable_in_app,
            categories=[item.model_dump() for item in request.categories],
        )
    ).model_dump()


@app.post("/engagement/device-tokens")
def post_device_token(
    http_request: Request,
    request: DeviceTokenRegisterRequest,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    payload = register_device_token(
        user_id=current_user.user_id,
        token=request.token,
        platform=request.platform,
        device_name=request.device_name,
        app_version=request.app_version,
        locale=request.locale,
    )
    return DeviceTokenEnvelopeResponse(token=payload).model_dump()


@app.delete("/engagement/device-tokens/{token_id}")
def delete_device_token_endpoint(
    token_id: str,
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    deleted = delete_device_token(user_id=current_user.user_id, token_id=token_id)
    if not deleted:
        raise_api_error(
            status_code=404,
            code="device_token_not_found",
            message="Device token was not found.",
        )
    return {"status": "ok"}


@app.patch("/engagement/notifications/{notification_id}/read")
def patch_notification_read(
    notification_id: str,
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_authenticated_user),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    payload = mark_notification_as_read(
        user_id=current_user.user_id,
        notification_id=notification_id,
    )
    if payload is None:
        raise_api_error(
            status_code=404,
            code="notification_not_found",
            message="Notification was not found.",
        )
    return NotificationReadResponse.model_validate(payload).model_dump()


@app.get("/admin")
def admin_only(
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_admin_permission("admin.access")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    return {
        "message": "Admin access granted.",
        "user": serialize_current_user(current_user),
    }


@app.get("/admin/summary")
def admin_summary(
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_admin_permission("admin.summary.read")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    return {
        "summary": get_dashboard_summary(),
        "user": serialize_current_user(current_user),
    }


@app.get("/admin/permissions")
def admin_permissions(
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_admin_permission("roles.read")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    permissions = [
        PermissionDefinitionResponse.model_validate(item).model_dump()
        for item in get_permission_catalog()
    ]
    return {
        "permissions": permissions,
        "user": serialize_current_user(current_user),
    }


@app.get("/admin/roles")
def admin_roles_list(
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_admin_permission("roles.read")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    roles = [RoleResponse.model_validate(item).model_dump() for item in list_roles()]
    return {
        "roles": roles,
        "user": serialize_current_user(current_user),
    }


@app.post("/admin/roles")
def admin_roles_create(
    http_request: Request,
    request: RoleCreateRequest,
    current_user: AuthenticatedUser = Depends(require_admin_permission("roles.manage")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    role = create_role(
        actor_user_id=current_user.user_id,
        role_name=request.name,
        display_name=request.display_name,
        description=request.description,
        permissions=request.permissions,
    )
    return {"role": RoleResponse.model_validate(role).model_dump()}


@app.patch("/admin/roles/{role_name}")
def admin_roles_update(
    role_name: str,
    http_request: Request,
    request: RoleUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_admin_permission("roles.manage")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    role = update_role(
        actor_user_id=current_user.user_id,
        role_name=role_name,
        display_name=request.display_name,
        description=request.description,
        permissions=request.permissions,
    )
    return {"role": RoleResponse.model_validate(role).model_dump()}


@app.get("/admin/users")
def admin_users_list(
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_admin_permission("users.read")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    users = [AdminUserResponse.model_validate(item).model_dump() for item in list_admin_users()]
    return {
        "users": users,
        "user": serialize_current_user(current_user),
    }


@app.post("/admin/users")
def admin_users_create(
    http_request: Request,
    request: AdminUserCreateRequest,
    current_user: AuthenticatedUser = Depends(require_admin_permission("users.manage")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    user = create_admin_user(
        actor_user_id=current_user.user_id,
        email=request.email,
        password=request.password,
        full_name=request.full_name,
        role=request.role,
        is_active=request.is_active,
    )
    return {"user": AdminUserResponse.model_validate(user).model_dump()}


@app.get("/admin/users/{user_id}")
def admin_user_detail(
    user_id: str,
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_admin_permission("users.read")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    user = get_admin_user(user_id)
    return {"user": AdminUserResponse.model_validate(user).model_dump()}


@app.patch("/admin/users/{user_id}")
def admin_user_update(
    user_id: str,
    http_request: Request,
    request: AdminUserUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_admin_permission("users.manage")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    user = update_admin_user(
        actor_user_id=current_user.user_id,
        user_id=user_id,
        role=request.role,
        is_active=request.is_active,
    )
    return {"user": AdminUserResponse.model_validate(user).model_dump()}


@app.put("/admin/users/{user_id}/permissions")
def admin_user_permissions_update(
    user_id: str,
    http_request: Request,
    request: UserPermissionOverrideUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_admin_permission("users.manage")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    user = update_user_permissions(
        actor_user_id=current_user.user_id,
        user_id=user_id,
        granted_permissions=request.granted_permissions,
        revoked_permissions=request.revoked_permissions,
    )
    return {"user": AdminUserResponse.model_validate(user).model_dump()}


@app.get("/admin/activity-logs")
def admin_activity_logs(
    http_request: Request,
    limit: int = 50,
    actor_user_id: str | None = None,
    target_user_id: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    current_user: AuthenticatedUser = Depends(require_admin_permission("activity.read")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    items = get_activity_logs(
        limit=limit,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        action=action,
        entity_type=entity_type,
    )
    return {
        "items": [ActivityLogResponse.model_validate(item).model_dump() for item in items],
        "user": serialize_current_user(current_user),
    }


@app.get("/admin/dashboard", response_class=HTMLResponse)
def admin_dashboard(
    http_request: Request,
    token: str | None = None,
) -> HTMLResponse:
    access_token = (token or "").strip()
    if not access_token:
        access_token = (http_request.cookies.get("admin_access_token") or "").strip()
    if not access_token:
        authorization = http_request.headers.get("authorization", "")
        scheme, _, bearer_token = authorization.partition(" ")
        if scheme.lower() == "bearer" and bearer_token.strip():
            access_token = bearer_token.strip()

    if not access_token:
        return HTMLResponse(render_admin_login(), status_code=401)

    try:
        current_user = require_admin_access_token(access_token)
        enforce_rate_limit(http_request, user=current_user)
    except HTTPException as exc:
        message = (
            exc.detail.get("message", "Authentication failed.")
            if isinstance(exc.detail, dict)
            else str(exc.detail)
        )
        return HTMLResponse(render_admin_login(error_message=message), status_code=exc.status_code)

    return HTMLResponse(
        render_admin_dashboard(
            summary=get_dashboard_summary(),
            current_user=current_user,
            token=access_token,
        )
    )


@app.get("/admin/dashboard/login", response_class=HTMLResponse)
def admin_dashboard_login_page() -> HTMLResponse:
    return HTMLResponse(render_admin_login())


@app.post("/admin/dashboard/login")
def admin_dashboard_login_submit(
    request: LoginRequest,
):
    try:
        session = authenticate_user(email=request.email, password=request.password)
    except HTTPException as exc:
        message = (
            exc.detail.get("message", "Authentication failed.")
            if isinstance(exc.detail, dict)
            else str(exc.detail)
        )
        return JSONResponse({"message": message}, status_code=exc.status_code)

    user = session.get("user") if isinstance(session, dict) else None
    permissions = (user or {}).get("permissions") if isinstance(user, dict) else None
    if not isinstance(permissions, list) or "admin.access" not in permissions:
        return JSONResponse(
            {"message": "هذا الحساب لا يملك صلاحية الدخول إلى لوحة المسؤول."},
            status_code=403,
        )

    response = JSONResponse({"status": "ok", "redirect_to": "/admin/dashboard"})
    response.set_cookie(
        "admin_access_token",
        str(session["access_token"]),
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=max(60, int(settings.access_token_ttl_seconds)),
    )
    return response


@app.get("/admin/dashboard/logout")
def admin_dashboard_logout() -> RedirectResponse:
    response = RedirectResponse(url="/admin/dashboard/login", status_code=303)
    response.delete_cookie("admin_access_token")
    return response


@app.get("/users")
def users_list(
    http_request: Request,
    current_user: AuthenticatedUser = Depends(require_permission("users.read")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    return {
        "users": list_users(),
    }


@app.patch("/users/{user_id}/role")
def patch_user_role(
    user_id: str,
    http_request: Request,
    request: UpdateUserRoleRequest,
    current_user: AuthenticatedUser = Depends(require_permission("users.manage")),
) -> dict[str, object]:
    enforce_rate_limit(http_request, user=current_user)
    user = update_admin_user(
        actor_user_id=current_user.user_id,
        user_id=user_id,
        role=request.role,
    )
    return {
        "user": AdminUserResponse.model_validate(user).model_dump(),
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
        from app.chat import answer_question
    except ImportError:
        from chat import answer_question  # type: ignore
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
        from app.retrieve import search
    except ImportError:
        from retrieve import search  # type: ignore
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
