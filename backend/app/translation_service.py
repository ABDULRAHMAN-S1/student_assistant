from __future__ import annotations

from functools import lru_cache

from app.config import get_settings


ARABIC_PATTERN = __import__("re").compile(r"[\u0600-\u06FF]")

try:
    from deep_translator import GoogleTranslator
except ImportError:  # pragma: no cover
    GoogleTranslator = None  # type: ignore


class TranslationUnavailable(RuntimeError):
    pass


def contains_arabic(text: str) -> bool:
    return bool(ARABIC_PATTERN.search(text or ""))


@lru_cache(maxsize=2)
def _get_google_translator(target: str) -> object:
    if GoogleTranslator is None:
        raise TranslationUnavailable("Translation dependency is not installed.")
    return GoogleTranslator(source="auto", target=target)


def translate_text(text: str) -> dict[str, str]:
    settings = get_settings()
    cleaned = (text or "").strip()
    if not cleaned:
        return {"translated_text": "", "target_language_code": "en"}

    if not settings.enable_translation:
        raise TranslationUnavailable("Translation is disabled by configuration.")

    if settings.translation_provider != "google" or not settings.allow_external_translation:
        raise TranslationUnavailable("No approved translation provider is configured.")

    target_language = "en" if contains_arabic(cleaned) else "ar"
    translator = _get_google_translator(target_language)
    translated = translator.translate(cleaned)  # type: ignore[attr-defined]
    if not translated or not str(translated).strip():
        raise TranslationUnavailable("Translation provider returned an empty result.")
    return {
        "translated_text": str(translated).strip(),
        "target_language_code": target_language,
    }