from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOCAL_DEV_ORIGINS = (
    "http://localhost:3000",
    "http://localhost:5000",
    "http://localhost:8000",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5000",
    "http://127.0.0.1:8000",
)


def _read_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _read_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value.strip())
    except ValueError:
        return default


def _read_list(name: str) -> tuple[str, ...]:
    raw_value = os.getenv(name, "")
    items = tuple(item.strip() for item in raw_value.split(",") if item.strip())
    return items


@dataclass(frozen=True)
class Settings:
    app_env: str
    api_title: str
    api_version: str
    db_path: Path
    log_level: str
    cors_origins: tuple[str, ...]
    jwt_secret: str
    access_token_ttl_seconds: int
    refresh_token_ttl_seconds: int
    require_https: bool
    trust_forwarded_proto: bool
    enable_api_docs: bool
    enable_translation: bool
    allow_external_translation: bool
    translation_provider: str
    redis_url: str | None

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "development").strip().lower() or "development"
    configured_origins = _read_list("CORS_ORIGINS")
    cors_origins = configured_origins or (() if app_env == "production" else LOCAL_DEV_ORIGINS)

    db_path = Path(os.getenv("APP_DB_PATH", str(DATA_DIR / "app.db"))).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    return Settings(
        app_env=app_env,
        api_title=os.getenv("API_TITLE", "Student Assistant API"),
        api_version=os.getenv("API_VERSION", "2.0.0"),
        db_path=db_path,
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        cors_origins=cors_origins,
        jwt_secret=os.getenv("JWT_SECRET", "development-only-change-me"),
        access_token_ttl_seconds=_read_int("ACCESS_TOKEN_TTL_SECONDS", 900),
        refresh_token_ttl_seconds=_read_int("REFRESH_TOKEN_TTL_SECONDS", 604800),
        require_https=_read_bool("REQUIRE_HTTPS", app_env == "production"),
        trust_forwarded_proto=_read_bool("TRUST_FORWARDED_PROTO", True),
        enable_api_docs=_read_bool("ENABLE_API_DOCS", app_env != "production"),
        enable_translation=_read_bool("ENABLE_TRANSLATION", False),
        allow_external_translation=_read_bool("ALLOW_EXTERNAL_TRANSLATION", False),
        translation_provider=os.getenv("TRANSLATION_PROVIDER", "disabled").strip().lower() or "disabled",
        redis_url=(os.getenv("REDIS_URL", "").strip() or None),
    )