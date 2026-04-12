from __future__ import annotations

import re

try:
    from app.question_analysis_utils import list_like_question_kind
    from app.retrieve import normalize_for_matching
except ImportError:
    from question_analysis_utils import list_like_question_kind  # type: ignore
    from retrieve import normalize_for_matching  # type: ignore


LIST_ITEM_PATTERN = re.compile(
    r"^(?:[-•▪]|[\d٠-٩]+(?:\s*[-–]\s*[\d٠-٩]+)?[\.\):：،-]?|[أ-ي][\.\):：،-])\s*"
)


def is_heading_like_line(line: str) -> bool:
    stripped = (line or "").strip()
    if not stripped or LIST_ITEM_PATTERN.match(stripped):
        return False

    normalized = normalize_for_matching(stripped)
    return any(
        normalized.startswith(prefix)
        for prefix in (
            "الفصل ",
            "الباب ",
            "القسم ",
            "المادة ",
            "القاعده التنفيذيه",
            "اولا",
            "ثانيا",
            "ثالثا",
            "رابعا",
            "خامسا",
            "سادسا",
            "سابعا",
            "ثامنا",
            "تاسعا",
            "عاشرا",
            "قبل الاختبار",
            "اثناء الاختبار",
            "بعد الاختبار",
            "سلم التقديرات",
            "نظام التقديرات",
        )
    ) or normalized.endswith(":")


def is_rule_like_line(line: str) -> bool:
    stripped = (line or "").strip()
    if not stripped or "[غير واضح في المصدر]" in stripped:
        return False

    normalized = normalize_for_matching(stripped)
    if "الصفحه" in normalized or normalized.endswith("الصفحه"):
        return False
    if LIST_ITEM_PATTERN.match(stripped):
        return True

    return any(
        phrase in normalized
        for phrase in (
            "لا يجوز",
            "لا يسمح",
            "يجوز",
            "يسمح",
            "يحق",
            "يجب",
            "يلتزم",
            "تلتزم",
            "الا يكون",
            "ان يكون",
            "عدم ",
            "منع ",
            "الحد الاعلي",
            "الحد الادني",
            "ممتاز",
            "جيد جدا",
            "مقبول",
            "راسب",
            "محروم",
            "منسحب",
        )
    )


def strip_list_marker(line: str) -> str:
    return LIST_ITEM_PATTERN.sub("", (line or "").strip(), count=1).strip()


def normalize_answer_item(line: str) -> str:
    cleaned = strip_list_marker(line)
    cleaned = cleaned.rstrip(" .،؛")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def build_answer_item_text(question: str, line: str) -> str:
    stripped = (line or "").strip().rstrip(" .،؛")
    normalized_stripped = normalize_for_matching(stripped)
    if list_like_question_kind(question) == "system" and (
        re.match(r"^[\d٠-٩]+\s*[-–]\s*[\d٠-٩]+", stripped)
        or re.match(r"^\d+\s+(?:الي|الى)\s+اقل", normalized_stripped)
    ):
        return re.sub(r"\s+", " ", stripped).strip()
    return normalize_answer_item(line)


def anchored_block_indices(lines: list[str], anchor_index: int) -> list[int]:
    if not lines or anchor_index < 0 or anchor_index >= len(lines):
        return []

    start = anchor_index
    while start > 0 and not is_heading_like_line(lines[start - 1]):
        start -= 1

    end = anchor_index
    while end + 1 < len(lines) and not is_heading_like_line(lines[end + 1]):
        end += 1

    return list(range(start, end + 1))