from __future__ import annotations

import re
from typing import Any

try:
    from app.retrieve import (
        STATUS_CODE_TOKENS,
        build_query_profile,
        is_code_style_query,
        normalize_for_matching,
        tokenize_text,
    )
except ImportError:
    from retrieve import (  # type: ignore
        STATUS_CODE_TOKENS,
        build_query_profile,
        is_code_style_query,
        normalize_for_matching,
        tokenize_text,
    )

STATUS_CODE_ENGLISH_MEANINGS = {
    "DN": "Deprived from final exam",
    "IC": "Incomplete",
    "NP": "Pass without grade",
    "W": "Withdrawn with excuse",
}
STATUS_CODE_ARABIC_MEANINGS = {
    "DN": "محروم من الاختبار النهائي",
    "IC": "غير مكتمل",
    "NP": "ناجح دون تقدير",
    "W": "منسحب بعذر",
}
STATUS_CODE_LINE_PATTERN = re.compile(r"\s*=\s*")


def extract_status_code_terms(question: str) -> list[str]:
    seen: set[str] = set()
    codes: list[str] = []
    for token in tokenize_text(question):
        if token in STATUS_CODE_TOKENS and token not in seen:
            seen.add(token)
            codes.append(token)
    return codes


def is_status_code_query(question: str) -> bool:
    query_profile = build_query_profile(question)
    codes = extract_status_code_terms(question)
    return is_code_style_query(query_profile, codes)


def status_code_context_article_matches(context: dict[str, Any], codes: list[str]) -> set[str]:
    article_text = normalize_for_matching(context.get("metadata", {}).get("article", ""))
    if not article_text:
        return set()
    return {code for code in codes if article_text == code or article_text.startswith(f"{code} ")}


def select_minimal_status_code_contexts(
    details_list: list[dict[str, Any]],
    codes: list[str],
    *,
    max_items: int,
) -> tuple[list[dict[str, Any]], set[str], int]:
    remaining = set(codes)
    selected: list[dict[str, Any]] = []
    definition_coverage: set[str] = set()

    for details in details_list:
        new_codes = details["exact_matches"] & remaining
        if not new_codes and selected:
            continue
        if not details["exact_matches"] and not details["definition_matches"]:
            continue

        selected.append(details["context"])
        remaining -= new_codes
        definition_coverage |= details["definition_matches"]

        if not remaining or len(selected) >= max_items:
            break

    covered = set(codes) - remaining
    return selected, covered, len(definition_coverage)


def extract_status_code_meaning_from_text(text: str, code: str) -> str:
    normalized_code = code.lower()
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        normalized_line = f" {normalize_for_matching(line)} "
        if not line or f" {normalized_code} " not in normalized_line:
            continue

        label_match = re.search(rf"\b{re.escape(code)}\b\s*\(([^)]+)\)", line, flags=re.IGNORECASE)
        if label_match:
            return label_match.group(1).strip(" :،")

        parts = [part.strip(" :،") for part in STATUS_CODE_LINE_PATTERN.split(line) if part.strip(" :،")]
        for index, part in enumerate(parts):
            if normalize_for_matching(part) != normalized_code:
                continue
            if index > 0:
                return parts[index - 1].rstrip(" :،")

        return line.rstrip(" :،")
    return ""


def extract_status_code_description_from_text(text: str, code: str) -> str:
    normalized_code = code.lower()
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        normalized_line = f" {normalize_for_matching(line)} "
        if not line or f" {normalized_code} " not in normalized_line:
            continue
        if "الوصف" not in normalize_for_matching(line):
            continue

        description = line
        if "الوصف" in line:
            description = line.split("الوصف", 1)[1]
        if ":" in description:
            description = description.split(":", 1)[1]
        return description.strip(" :،").rstrip(" .،")
    return ""
