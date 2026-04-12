from __future__ import annotations

from typing import Any

try:
    from app.retrieve import light_stem, normalize_for_matching, tokenize_text
except ImportError:
    from retrieve import light_stem, normalize_for_matching, tokenize_text  # type: ignore


ARABIC_STOPWORDS = {
    "هل",
    "ما",
    "ماذا",
    "متى",
    "كيف",
    "اذا",
    "إذا",
    "في",
    "من",
    "على",
    "عن",
    "الى",
    "إلى",
    "مع",
    "داخل",
    "خلال",
    "بعد",
    "قبل",
    "يمكن",
    "استطيع",
    "أستطيع",
    "يحدث",
}


def build_question_stems(question: str, language: str) -> list[str]:
    if language != "ar":
        return []

    stems: list[str] = []
    seen: set[str] = set()
    for token in tokenize_text(question):
        if token in ARABIC_STOPWORDS or len(token) < 2:
            continue
        stem = light_stem(token)
        if len(stem) < 2 or stem in seen:
            continue
        seen.add(stem)
        stems.append(stem)
    return stems


def explicit_source_type_preference(question: str) -> str | None:
    normalized_question = normalize_for_matching(question)
    if "سياس" in normalized_question:
        return "policy"
    if "دليل" in normalized_question:
        return "guide"
    if "اسئله شائعه" in normalized_question or "faq" in normalized_question:
        return "faq"
    if "تقدير" in normalized_question:
        return "regulation"
    if "لائح" in normalized_question:
        return "regulation"
    return None


def list_like_question_kind(question: str) -> str | None:
    normalized_question = normalize_for_matching(question)
    if any(term in normalized_question for term in ("شروط", "متطلبات")):
        return "conditions"
    if "ضوابط" in normalized_question:
        return "rules"
    if "خطوات" in normalized_question:
        return "steps"
    if "عقوب" in normalized_question:
        return "penalties"
    if "حالات" in normalized_question or normalized_question.startswith("متي") or " متي " in f" {normalized_question} ":
        return "cases"
    if "سياس" in normalized_question:
        return "policy"
    if "تقدير" in normalized_question or "سلم" in normalized_question or "نظام" in normalized_question:
        return "system"
    return None


def infer_context_scope_hint(question: str, contexts: list[dict[str, Any]]) -> str:
    if not contexts:
        return ""

    normalized_question = normalize_for_matching(question)
    context_texts = [
        normalize_for_matching(
            " ".join(
                part
                for part in (
                    context.get("metadata", {}).get("section", ""),
                    context.get("metadata", {}).get("article", ""),
                    context.get("metadata", {}).get("document_title", ""),
                )
                if part
            )
        )
        for context in contexts[:4]
    ]
    context_texts = [text for text in context_texts if text]
    if not context_texts:
        return ""

    scope_markers = (
        (("الإسكان الطلابي", "الاسكان الطلابي", "السكن الجامعي", "السكن"), "فيما يتعلق بالإسكان الطلابي"),
        (("المقررات العامة والاختيارية",), "فيما يتعلق بالمقررات العامة والاختيارية"),
        (("التقديرات", "المعدل"), "فيما يتعلق بالتقديرات والمعدل"),
        (("الحضور", "الغياب", "الحرمان"), "فيما يتعلق بالحضور والغياب"),
    )

    minimum_hits = 2 if len(context_texts) >= 2 else 1
    for markers, label in scope_markers:
        if any(marker in normalized_question for marker in markers):
            continue
        hit_count = sum(1 for text in context_texts if any(marker in text for marker in markers))
        if hit_count >= minimum_hits:
            return label
    return ""