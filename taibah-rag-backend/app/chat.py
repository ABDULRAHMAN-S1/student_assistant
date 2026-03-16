from __future__ import annotations

import argparse
import json
import re
import sys
from functools import lru_cache
from typing import Any

from deep_translator import GoogleTranslator

try:
    from app.retrieve import (
        build_query_profile,
        detect_language,
        get_chunk_records,
        light_stem,
        normalize_for_matching,
        search,
        tokenize_text,
    )
except ImportError:
    from retrieve import (  # type: ignore
        build_query_profile,
        detect_language,
        get_chunk_records,
        light_stem,
        normalize_for_matching,
        search,
        tokenize_text,
    )


FALLBACK_AR = "لم أجد إجابة صريحة في اللوائح المتاحة."
FALLBACK_EN = "I could not find an explicit answer in the available regulations."
UNCLEAR_AR = "النص المسترجع غير واضح في هذه النقطة."
UNCLEAR_EN = "The retrieved text is unclear on this point."
ARABIC_GENERATION_PROMPT = """تعليمات بناء الإجابة:
- أجب مباشرة وباختصار.
- استخدم فقط النصوص المسترجعة.
- إذا لم توجد إجابة صريحة فقل: لم أجد إجابة صريحة في اللوائح المتاحة.
- إذا كان النص غير واضح أو ناقصاً فاذكر ذلك بوضوح.
- اذكر المادة أو القسم أو اسم اللائحة عند الإمكان.
"""
ENGLISH_GENERATION_PROMPT = """Answering rules:
- Answer directly and briefly.
- Use only the retrieved regulation text.
- If no explicit answer is found, say so clearly.
- If the retrieved text is unclear, say that it is unclear.
- Mention the article, section, or regulation source when helpful.
"""
ARABIC_OUTPUT_TEMPLATE = "{direct_answer}\nالمرجع: {reference}"
ENGLISH_OUTPUT_TEMPLATE = "{direct_answer}\nSource: {reference}"
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
YES_NO_PATTERN_EN = re.compile(r"^(can|is|are|do|does|did|will|may|should)\b", re.IGNORECASE)
POSITIVE_AR = ("يجوز", "يسمح", "يحق")
NEGATIVE_AR = ("لا يسمح", "لا يجوز", "عدم", "محظور", "ممنوع")
CLAUSE_NUMBER_PATTERN = re.compile(r"(?<!\d)\b\d+\.\s*")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[\.\!\؟])\s+|\n+")
NUMBER_PATTERN = re.compile(r"[\d٠-٩]+")
MIN_ARABIC_TOP_SCORE = 0.34


def truncate_text(text: str, limit: int = 700) -> str:
    cleaned = (text or "").strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip() + "..."


def asks_upper_limit(normalized_question: str) -> bool:
    return "حد" in normalized_question and "اعلي" in normalized_question


def asks_lower_limit(normalized_question: str) -> bool:
    return "حد" in normalized_question and "ادني" in normalized_question


def extract_limit_number_text(text: str) -> str:
    cleaned = CLAUSE_NUMBER_PATTERN.sub("", (text or "").strip()).strip()
    if not cleaned:
        return ""
    normalized = normalize_for_matching(cleaned)
    if not NUMBER_PATTERN.search(cleaned):
        return ""
    if not any(term in normalized for term in ("حد", "عبء", "ساع", "وحد")):
        return ""
    return cleaned


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


@lru_cache(maxsize=1)
def get_ar_to_en_translator() -> GoogleTranslator:
    return GoogleTranslator(source="ar", target="en")


def translate_to_english(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    translator = get_ar_to_en_translator()
    try:
        return translator.translate(cleaned)
    except Exception:
        return cleaned


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        normalized = normalize_for_matching(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(item.strip())
    return deduped


def dedupe_answer_text(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    sentences = [part.strip() for part in SENTENCE_SPLIT_PATTERN.split(cleaned) if part.strip()]
    deduped_sentences = dedupe_preserve_order(sentences)
    if not deduped_sentences:
        return cleaned

    return " ".join(deduped_sentences).strip()


def is_yes_no_question(question: str, language: str) -> bool:
    stripped = (question or "").strip()
    if language == "ar":
        return stripped.startswith("هل")
    return bool(YES_NO_PATTERN_EN.match(stripped))


def is_comparison_question(question: str) -> bool:
    normalized_question = normalize_for_matching(question)
    return any(
        phrase in normalized_question
        for phrase in (
            "ما الفرق بين",
            "الفرق بين",
            "قارن بين",
        )
    )


def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_SPLIT_PATTERN.split((text or "").strip()) if part.strip()]


def limit_answer_sentences(text: str, max_sentences: int = 3) -> str:
    sentences = dedupe_preserve_order(split_sentences(text))
    if not sentences:
        return (text or "").strip()
    return " ".join(sentences[:max_sentences]).strip()


def strip_leading_connector(text: str) -> str:
    return re.sub(r"^(لكن|كما|وإذا|واذا)\s+", "", (text or "").strip())


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


def build_removable_metadata_lines(metadata: dict[str, Any]) -> set[str]:
    removable: set[str] = set()
    for value in (
        metadata.get("article", ""),
        metadata.get("document_title", ""),
        metadata.get("title", ""),
    ):
        normalized = normalize_for_matching(value)
        if normalized:
            removable.add(normalized)

    section = metadata.get("section", "")
    for part in section.split(">"):
        normalized = normalize_for_matching(part.strip())
        if normalized:
            removable.add(normalized)

    return removable


def clean_context_lines(context: dict[str, Any]) -> list[str]:
    metadata = context.get("metadata", {})
    removable = build_removable_metadata_lines(metadata)
    lines = []
    previous = ""
    for raw_line in context.get("content", "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        normalized = normalize_for_matching(line)
        if normalized in removable and normalized:
            continue
        if normalized == previous:
            continue
        previous = normalized
        lines.append(line)
    return lines


def score_line(line: str, question_stems: list[str]) -> float:
    normalized_line = normalize_for_matching(line)
    line_stems = {light_stem(token) for token in tokenize_text(line)}
    overlap = sum(1 for stem in question_stems if stem in line_stems)
    score = float(overlap)

    if any(marker in normalized_line for marker in ("لا يسمح", "لا يجوز", "يجوز", "يسمح", "يحق")):
        score += 0.8
    if line.startswith(("المادة", "البند", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
        score += 0.2
    if "[غير واضح في المصدر]" in line:
        score -= 0.5
    return score


def context_answer_score(context: dict[str, Any], question_stems: list[str], language: str) -> float:
    base_score = float(context.get("score", 0.0))
    if language != "ar":
        return base_score

    metadata = context.get("metadata", {})
    metadata_text = " ".join(
        value for value in (metadata.get("article", ""), metadata.get("section", ""), metadata.get("title", "")) if value
    )
    metadata_stems = {light_stem(token) for token in tokenize_text(metadata_text)}
    metadata_overlap = sum(1 for stem in question_stems if stem in metadata_stems)

    best_line_score = 0.0
    for line in clean_context_lines(context):
        best_line_score = max(best_line_score, score_line(line, question_stems))

    if metadata.get("status") == "partial":
        base_score -= 0.08

    return (base_score * 2.2) + best_line_score + (metadata_overlap * 0.9)


def build_query_profile_for_answer(question: str, language: str) -> dict[str, Any]:
    if language == "ar":
        profile = build_query_profile(question)
        normalized_question = profile["normalized_query"]
        extra_stems: list[str] = []

        if any(term in normalized_question for term in ("غبت", "غاب", "غايب", "يغيب")):
            extra_stems.append("غيب")
        if "شروط" in normalized_question and any(term in normalized_question for term in ("سكن", "اسكان")):
            extra_stems.extend(["شرط", "سكن"])

        for stem in extra_stems:
            if stem not in profile["stems"]:
                profile["stems"].append(stem)
            if stem not in profile["important_stems"]:
                profile["important_stems"].append(stem)
            if stem not in profile["strong_stems"]:
                profile["strong_stems"].append(stem)

        return profile

    return {
        "normalized_query": normalize_for_matching(question),
        "tokens": [token.lower() for token in re.findall(r"[a-zA-Z]+", question)],
        "stems": [],
        "phrases": [],
        "important_stems": [],
        "strong_stems": [],
        "broad_stems": [],
    }


def context_group(context: dict[str, Any]) -> str:
    metadata = context.get("metadata", {})
    text = normalize_for_matching(
        " ".join(
            part
            for part in (
                metadata.get("document_title", ""),
                metadata.get("section", ""),
                metadata.get("article", ""),
            )
            if part
        )
    )
    if any(term in text for term in ("اسكان", "سكن")):
        return "housing"
    if any(term in text for term in ("الزي", "مظهر")):
        return "dress"
    if any(term in text for term in ("السلوك", "انضباط", "مخالف", "عقوب")):
        return "conduct"
    return "academic"


def query_flags(query_profile: dict[str, Any]) -> dict[str, bool]:
    normalized_query = query_profile["normalized_query"]
    stems = set(query_profile["stems"])
    return {
        "housing": bool({"سكن", "اسكان", "اقام"} & stems)
        or any(phrase in normalized_query for phrase in ("السكن الجامعي", "السكن الطلابي", "الاسكان الطلابي")),
        "dress": bool({"زي", "مظهر", "عباي", "لبس"} & stems)
        or any(phrase in normalized_query for phrase in ("الزي الجامعي", "المظهر العام")),
    }


def context_support_details(context: dict[str, Any], query_profile: dict[str, Any]) -> dict[str, float]:
    haystack = context_search_text(context)
    tokens = tokenize_text(haystack)
    token_set = set(tokens)
    stem_set = {light_stem(token) for token in token_set}
    metadata_text = normalize_for_matching(
        " ".join(
            part
            for part in (
                context.get("metadata", {}).get("article", ""),
                context.get("metadata", {}).get("section", ""),
                context.get("metadata", {}).get("document_title", ""),
            )
            if part
        )
    )

    token_matches = sum(1 for token in query_profile["tokens"] if token in token_set)
    stem_matches = sum(1 for stem in query_profile["stems"] if stem in stem_set)
    important_matches = sum(1 for stem in query_profile["important_stems"] if stem in stem_set)
    phrase_matches = sum(1 for phrase in query_profile["phrases"] if phrase in haystack)
    metadata_hits = sum(1 for token in query_profile["tokens"] if f" {token} " in f" {metadata_text} ")
    lexical_score = float(context.get("lexical_score", 0.0))
    semantic_score = float(context.get("semantic_score", context.get("score", 0.0)))
    score = (float(context.get("score", 0.0)) * 1.5) + (lexical_score * 2.4) + (token_matches * 0.35)
    score += (stem_matches * 0.55) + (important_matches * 0.9) + (phrase_matches * 1.2) + (metadata_hits * 0.45)

    flags = query_flags(query_profile)
    group = context_group(context)
    if group == "housing" and not flags["housing"]:
        score -= 0.55
    if group == "dress" and not flags["dress"]:
        score -= 0.65
    if context.get("metadata", {}).get("status") == "partial":
        score -= 0.05

    important_ratio = 0.0
    if query_profile["important_stems"]:
        important_ratio = important_matches / len(query_profile["important_stems"])

    stem_ratio = 0.0
    if query_profile["stems"]:
        stem_ratio = stem_matches / len(query_profile["stems"])

    return {
        "support_score": score,
        "token_matches": float(token_matches),
        "stem_matches": float(stem_matches),
        "important_matches": float(important_matches),
        "phrase_matches": float(phrase_matches),
        "metadata_hits": float(metadata_hits),
        "lexical_score": lexical_score,
        "semantic_score": semantic_score,
        "important_ratio": important_ratio,
        "stem_ratio": stem_ratio,
    }


def passes_relevance_gate(
    question: str,
    context: dict[str, Any],
    query_profile: dict[str, Any],
    details: dict[str, float],
    language: str,
) -> bool:
    if language != "ar":
        return float(context.get("score", 0.0)) >= 0.35

    top_score = float(context.get("score", 0.0))
    if top_score < MIN_ARABIC_TOP_SCORE:
        return False

    if details["phrase_matches"] > 0:
        return True

    if query_profile["important_stems"]:
        if details["important_matches"] <= 0:
            return False
        if len(query_profile["important_stems"]) >= 2 and details["important_ratio"] < 0.5:
            return False
        if details["lexical_score"] < 0.18 and details["stem_ratio"] < 0.5:
            return False

    if len(query_profile["stems"]) >= 2 and details["stem_ratio"] < 0.5 and details["lexical_score"] < 0.4:
        return False

    if details["stem_matches"] <= 0 and details["lexical_score"] < 0.2:
        return False

    return True


def filter_contexts_for_generation(
    question: str,
    contexts: list[dict[str, Any]],
    language: str,
) -> list[dict[str, Any]]:
    if not contexts:
        return []

    mode = detect_answer_mode(question, language) if language == "ar" else "general"
    if language == "ar":
        if mode == "load_limit":
            normalized_question = normalize_for_matching(question)
            relevant_contexts = [
                context
                for context in contexts
                if any(
                    term in context_search_text(context)
                    for term in (
                        "العبء الدراسي",
                        "الحد الاعلي للعبء الدراسي",
                        "الحد الادني للعبء الدراسي",
                        "الوحدات الدراسيه",
                        "يسمح للطالب التسجيل",
                        "محدده من مجلس الجامعه",
                        "اقل من الحد الادني للعبء الدراسي",
                    )
                )
            ]
            if asks_upper_limit(normalized_question):
                mode_contexts = [
                    context
                    for context in (
                        pick_context(
                            relevant_contexts,
                            article_terms=("الحد الاعلي للعبء الدراسي",),
                            include_any=("الحد الاعلي للعبء الدراسي", "العبء الدراسي"),
                        ),
                        pick_context(
                            relevant_contexts,
                            article_terms=("العبء الدراسي",),
                            include_any=("محدده من مجلس الجامعه", "يسمح للطالب التسجيل", "العبء الدراسي"),
                        ),
                    )
                    if context is not None
                ]
            elif asks_lower_limit(normalized_question):
                mode_contexts = [
                    context
                    for context in (
                        pick_context(
                            relevant_contexts,
                            article_terms=("الحد الادني للعبء الدراسي",),
                            include_any=("الحد الادني للعبء الدراسي", "العبء الدراسي"),
                        ),
                        pick_context(
                            relevant_contexts,
                            include_any=("اقل من الحد الادني للعبء الدراسي", "لا يسمح للطالب الانسحاب"),
                            article_terms=("البند 4",),
                        ),
                        pick_context(
                            relevant_contexts,
                            article_terms=("العبء الدراسي",),
                            include_any=("العبء الدراسي", "يسمح للطالب التسجيل"),
                        ),
                    )
                    if context is not None
                ]
            else:
                mode_contexts = [
                    context
                    for context in (
                        pick_context(
                            relevant_contexts,
                            article_terms=("العبء الدراسي",),
                            include_any=("العبء الدراسي", "يسمح للطالب التسجيل", "الوحدات الدراسيه"),
                        ),
                        pick_context(
                            relevant_contexts,
                            article_terms=("الحد الاعلي للعبء الدراسي", "الحد الادني للعبء الدراسي"),
                            include_any=("العبء الدراسي", "الوحدات الدراسيه"),
                        ),
                    )
                    if context is not None
                ]
            if mode_contexts:
                return dedupe_preserve_order_contexts(mode_contexts)
        if mode == "missed_final":
            mode_contexts = rank_contexts_by_terms(
                contexts,
                include_any=("غبت", "غاب", "غايب", "يغيب", "صفر", "اختبار بديل"),
                prefer_article=("المادة الحادية والثلاثون", "المادة الثانية والثلاثون"),
            )[:3]
            if mode_contexts:
                return dedupe_preserve_order_contexts(mode_contexts)
        if mode == "penalty":
            mode_contexts = rank_contexts_by_terms(
                contexts,
                include_any=("عقوب", "غش", "الاختبار النهائي", "راسب", "فصل"),
                prefer_article=("العقوبات", "الإجراءات المتبعة في حالة الغش"),
            )[:3]
            if mode_contexts:
                return dedupe_preserve_order_contexts(mode_contexts)
        if mode == "lecture_recording":
            mode_contexts = rank_contexts_by_terms(
                contexts,
                require_all=("تصوير", "محاضر"),
                include_any=("موافقه", "موافقة", "تسجيل"),
            )[:2]
            if mode_contexts:
                return dedupe_preserve_order_contexts(mode_contexts)

    query_profile = build_query_profile_for_answer(question, language)
    mode_priority: dict[str, float] = {}

    if mode == "missed_final":
        for index, context in enumerate(
            rank_contexts_by_terms(
                contexts,
                include_any=("غبت", "غاب", "غايب", "يغيب", "صفر", "اختبار بديل"),
                prefer_article=("المادة الحادية والثلاثون", "المادة الثانية والثلاثون"),
            )[:4]
        ):
            mode_priority[context["id"]] = 1.4 - (index * 0.2)
    elif mode == "penalty":
        for index, context in enumerate(
            rank_contexts_by_terms(
                contexts,
                include_any=("عقوب", "غش", "الاختبار النهائي", "راسب", "فصل"),
                prefer_article=("العقوبات",),
            )[:4]
        ):
            mode_priority[context["id"]] = 1.2 - (index * 0.15)
    elif mode == "housing_conditions":
        for index, context in enumerate(
            rank_contexts_by_terms(
                contexts,
                include_any=("شروط", "الاسكان", "السكن الجامعي", "قبول"),
            )[:4]
        ):
            mode_priority[context["id"]] = 1.0 - (index * 0.1)

    scored: list[tuple[float, dict[str, Any], dict[str, float]]] = []
    for context in contexts:
        details = context_support_details(context, query_profile)
        scored.append((details["support_score"] + mode_priority.get(context["id"], 0.0), context, details))

    scored.sort(key=lambda item: item[0], reverse=True)
    primary_score, primary_context, primary_details = scored[0]
    if not passes_relevance_gate(question, primary_context, query_profile, primary_details, language):
        return []

    primary_metadata = primary_context.get("metadata", {})
    primary_document = primary_metadata.get("document_title", "")
    primary_section = primary_metadata.get("section", "")
    anchor_same_section = int(primary_details["metadata_hits"]) > 0 or (
        language == "ar" and normalize_for_matching(primary_section) and any(
            stem in normalize_for_matching(primary_section) for stem in query_profile["stems"]
        )
    )

    filtered: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for support_score, context, details in scored:
        context_id = context["id"]
        if context_id in seen_ids:
            continue
        if context.get("metadata", {}).get("document_title", "") != primary_document:
            continue
        if anchor_same_section and context.get("metadata", {}).get("section", "") != primary_section:
            continue
        if support_score < primary_score - 1.25:
            continue
        if query_profile["important_stems"] and details["important_matches"] <= 0:
            continue
        if details["stem_matches"] <= 0 and details["lexical_score"] < 0.2:
            continue
        seen_ids.add(context_id)
        filtered.append(context)
        if len(filtered) == 3:
            break

    return filtered or [primary_context]


def select_answer_contexts(question: str, contexts: list[dict[str, Any]], language: str) -> list[dict[str, Any]]:
    if not contexts:
        return []

    if language != "ar":
        return contexts[:3]

    question_stems = build_question_stems(question, language)
    ranked = sorted(
        contexts,
        key=lambda item: context_answer_score(item, question_stems, language),
        reverse=True,
    )
    return ranked[:3]


def extract_snippet(context: dict[str, Any], question: str, language: str) -> str:
    lines = clean_context_lines(context)
    if not lines:
        return ""

    if language != "ar":
        return truncate_text(" ".join(lines[:3]), 320)

    question_stems = build_question_stems(question, language)
    scored_lines = [(score_line(line, question_stems), line) for line in lines]
    scored_lines.sort(key=lambda item: item[0], reverse=True)

    chosen: list[str] = []
    for score, line in scored_lines:
        if score <= 0.0 and chosen:
            continue
        chosen.append(line)
        if len(chosen) == 2:
            break

    if not chosen:
        chosen = lines[:2]
    return " ".join(dedupe_preserve_order(chosen))


def build_reference(contexts: list[dict[str, Any]], language: str) -> str:
    references: list[str] = []
    for context in contexts[:2]:
        metadata = context.get("metadata", {})
        parts = [
            (metadata.get("article", "") or "").rstrip(" :،"),
            (metadata.get("section", "") or "").rstrip(" :،"),
            (metadata.get("document_title", "") or "").rstrip(" :،"),
        ]
        reference = "، ".join(part for part in parts if part)
        if reference:
            references.append(reference)

    deduped = dedupe_preserve_order(references)
    if not deduped:
        return ""

    joined = " | ".join(deduped)
    return joined if language == "ar" else translate_to_english(joined)


def context_search_text(context: dict[str, Any]) -> str:
    metadata = context.get("metadata", {})
    parts = [
        metadata.get("article", ""),
        metadata.get("section", ""),
        metadata.get("document_title", ""),
        context.get("content", ""),
    ]
    return normalize_for_matching(" ".join(part for part in parts if part))


def fallback_load_limit_contexts(question: str, limit: int = 4) -> list[dict[str, Any]]:
    normalized_question = normalize_for_matching(question)
    asks_upper = asks_upper_limit(normalized_question)
    asks_lower = asks_lower_limit(normalized_question)

    candidates: list[tuple[float, dict[str, Any]]] = []
    for record in get_chunk_records():
        haystack = " ".join((record.get("normalized_metadata", ""), record.get("normalized_content", ""))).strip()
        metadata_text = record.get("normalized_metadata", "")

        if not any(
            term in haystack
            for term in (
                "العبء الدراسي",
                "الحد الاعلي للعبء الدراسي",
                "الحد الادني للعبء الدراسي",
                "الوحدات الدراسيه",
                "يسمح للطالب التسجيل",
                "اقل من الحد الادني للعبء الدراسي",
            )
        ):
            continue

        score = 0.0
        if "لائحه الدراسه والاختبارات" in metadata_text:
            score += 2.0
        if "العبء الدراسي" in haystack:
            score += 3.0
        if "الوحدات الدراسيه" in haystack:
            score += 1.5
        if "يسمح للطالب التسجيل" in haystack:
            score += 1.5
        if "محدده من مجلس الجامعه" in haystack:
            score += 1.0
        if "سكن" in metadata_text or "اسكان" in metadata_text:
            score -= 6.0

        if asks_upper:
            if "الحد الاعلي للعبء الدراسي" in haystack:
                score += 5.0
            else:
                score -= 1.0
        elif asks_lower:
            if "الحد الادني للعبء الدراسي" in haystack:
                score += 5.0
            if "اقل من الحد الادني للعبء الدراسي" in haystack:
                score += 2.0
        else:
            if "الحد الاعلي للعبء الدراسي" in haystack or "الحد الادني للعبء الدراسي" in haystack:
                score += 2.5

        if score <= 0:
            continue

        candidates.append(
            (
                score,
                {
                    "id": record["id"],
                    "content": record["content"],
                    "metadata": record["metadata"],
                    "score": score,
                },
            )
        )

    candidates.sort(key=lambda item: item[0], reverse=True)
    return [context for _, context in candidates[:limit]]


def detect_answer_mode(question: str, language: str) -> str:
    normalized_question = normalize_for_matching(question)
    lower_question = (question or "").lower()

    if (
        asks_upper_limit(normalized_question)
        or asks_lower_limit(normalized_question)
        or "عدد الساعات" in normalized_question
        or "رقم محدد" in normalized_question
    ) and any(term in normalized_question for term in ("ساع", "عبء", "وحد")):
        return "load_limit"
    if "كم" in normalized_question and any(term in normalized_question for term in ("ساع", "عبء", "وحد", "مسموح")):
        return "load_limit"
    if "شروط" in normalized_question and any(term in normalized_question for term in ("سكن", "اسكان")):
        return "housing_conditions"
    if "تصوير" in normalized_question and "محاضر" in normalized_question:
        return "lecture_recording"
    if "withdraw" in lower_question or "انسحاب" in normalized_question:
        return "withdrawal"
    if "smok" in lower_question or "تدخين" in normalized_question:
        return "smoking"
    if ("penalty" in lower_question or "cheat" in lower_question) or (
        "غش" in normalized_question and "عقوب" in normalized_question
    ):
        return "penalty"
    if "miss" in lower_question or "غبت" in normalized_question or "غاب" in normalized_question:
        if "exam" in lower_question or "اختبار" in normalized_question:
            return "missed_final"
    return "general"


def rank_contexts_by_terms(
    contexts: list[dict[str, Any]],
    *,
    require_all: tuple[str, ...] = (),
    include_any: tuple[str, ...] = (),
    prefer_article: tuple[str, ...] = (),
    exclude_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    excluded = exclude_ids or set()
    ranked: list[tuple[float, dict[str, Any]]] = []
    for context in contexts:
        if context["id"] in excluded:
            continue

        haystack = context_search_text(context)
        article_text = normalize_for_matching(context.get("metadata", {}).get("article", ""))
        score = float(context.get("score", 0.0)) * 2

        if require_all:
            matches = sum(1 for term in require_all if term in haystack)
            score += matches * 1.8
            if matches != len(require_all):
                score -= 3.0

        if include_any:
            score += sum(1.0 for term in include_any if term in haystack)

        if prefer_article:
            score += sum(1.4 for term in prefer_article if term in article_text)

        ranked.append((score, context))

    ranked.sort(key=lambda item: item[0], reverse=True)
    return [context for _, context in ranked]


def pick_context(
    contexts: list[dict[str, Any]],
    *,
    article_terms: tuple[str, ...] = (),
    require_all: tuple[str, ...] = (),
    include_any: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    for context in contexts:
        article_text = normalize_for_matching(context.get("metadata", {}).get("article", ""))
        haystack = context_search_text(context)
        if article_terms and not any(term in article_text for term in article_terms):
            continue
        if require_all and not all(term in haystack for term in require_all):
            continue
        if include_any and not any(term in haystack for term in include_any):
            continue
        return context

    ranked = rank_contexts_by_terms(
        contexts,
        require_all=require_all,
        include_any=include_any,
        prefer_article=article_terms,
    )
    return ranked[0] if ranked else None


def extract_matching_lines(
    context: dict[str, Any],
    *,
    require_all: tuple[str, ...] = (),
    include_any: tuple[str, ...] = (),
    limit: int = 2,
) -> str:
    matches: list[str] = []
    for line in clean_context_lines(context):
        normalized = normalize_for_matching(line)
        if require_all and not all(term in normalized for term in require_all):
            continue
        if include_any and not any(term in normalized for term in include_any):
            continue
        matches.append(line)
        if len(matches) == limit:
            break

    if matches:
        return " ".join(dedupe_preserve_order(matches))
    return ""


def trim_from_phrase(text: str, phrases: tuple[str, ...]) -> str:
    cleaned = (text or "").strip()
    for phrase in phrases:
        index = cleaned.find(phrase)
        if index >= 0:
            return cleaned[index:].strip()
    return cleaned


def build_comparison_label(context: dict[str, Any]) -> str:
    metadata = context.get("metadata", {})
    label = (
        metadata.get("article", "")
        or metadata.get("title", "")
        or (metadata.get("section", "").split(">")[-1].strip() if metadata.get("section", "") else "")
        or metadata.get("document_title", "")
    )
    return label.rstrip(" :،")


def build_comparison_arabic_answer(question: str, contexts: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    seen_labels: set[str] = set()

    for context in contexts[:3]:
        label = build_comparison_label(context)
        normalized_label = normalize_for_matching(label)
        if not label or normalized_label in seen_labels:
            continue

        snippet = extract_snippet(context, question, "ar")
        if not snippet:
            continue

        cleaned_snippet = CLAUSE_NUMBER_PATTERN.sub("", snippet).strip()
        if normalize_for_matching(cleaned_snippet).startswith(normalized_label):
            cleaned_snippet = cleaned_snippet[len(label) :].lstrip(" :،-")
        cleaned_snippet = limit_answer_sentences(polish_arabic_answer_text(cleaned_snippet), max_sentences=1)
        if not cleaned_snippet:
            continue

        seen_labels.add(normalized_label)
        lines.append(f"- {label}: {cleaned_snippet}")

    return "\n".join(lines)


def format_yes_no_arabic_answer(question: str, answer: str, contexts: list[dict[str, Any]]) -> str:
    cleaned = (answer or "").strip()
    if not cleaned or cleaned == FALLBACK_AR:
        return cleaned

    normalized_question = normalize_for_matching(question)
    normalized_answer = normalize_for_matching(cleaned)

    if "انسحاب" in normalized_question and asks_lower_limit(normalized_question):
        return "لا، لا يسمح بالانسحاب إذا أصبح العبء أقل من الحد الأدنى بعد تنفيذ الانسحاب."

    if cleaned.startswith("نعم،") or cleaned.startswith("لا،"):
        return limit_answer_sentences(cleaned, max_sentences=2)

    if "مجلس الجامعه" in normalized_question and any(
        "مجلس الجامعه" in context_search_text(context) and "محدد" in context_search_text(context)
        for context in contexts
    ):
        return "نعم، يظهر في النص أن العبء الدراسي محدد من مجلس الجامعة."

    if cleaned.startswith("لم أجد في النص المتاح رقم") or cleaned.startswith("لم أجد في النص المتاح عدد"):
        return f"لا، {cleaned}"

    if any(token in normalized_answer for token in ("لا يسمح", "لا يجوز", "ممنوع", "محظور")):
        body = strip_leading_connector(limit_answer_sentences(cleaned, max_sentences=1))
        if body.startswith("لا"):
            return f"لا، {body}"
        return f"لا، {body.rstrip(' .')}."

    if cleaned.startswith("نعم") or cleaned.startswith("لا"):
        return limit_answer_sentences(cleaned, max_sentences=2)

    if any(token in normalized_answer for token in ("يجوز", "يسمح", "يحق", "محدد من مجلس الجامعه")):
        body = strip_leading_connector(limit_answer_sentences(cleaned, max_sentences=1))
        return f"نعم، {body.rstrip(' .')}."

    return limit_answer_sentences(cleaned, max_sentences=2)


def format_arabic_direct_answer(question: str, answer: str, contexts: list[dict[str, Any]]) -> str:
    cleaned = (answer or "").strip()
    if not cleaned or cleaned == FALLBACK_AR:
        return cleaned

    if is_comparison_question(question):
        comparison_answer = build_comparison_arabic_answer(question, contexts)
        if comparison_answer:
            return comparison_answer

    if is_yes_no_question(question, "ar"):
        return format_yes_no_arabic_answer(question, cleaned, contexts)

    return limit_answer_sentences(cleaned, max_sentences=3)


def polish_arabic_answer_text(text: str) -> str:
    cleaned = CLAUSE_NUMBER_PATTERN.sub("", (text or "").strip())
    cleaned = cleaned.replace("ويذكر النص المسترجع من هذه العقوبات:", "ومن العقوبات المذكورة في النص:")
    cleaned = cleaned.replace(
        "عقوبة الغش أو محاولته مقصورة على إحدى العقوبات من البند 7 إلى البند 15:",
        "عقوبة الغش أو محاولته تقتصر على العقوبات الواردة من البند 7 إلى البند 15.",
    )
    cleaned = cleaned.replace("كما عدم التدخين", "وفي الإسكان الطلابي أيضاً: عدم التدخين")
    cleaned = cleaned.replace("، ويظهر في النص", ". ويظهر في النص")
    cleaned = cleaned.replace("، كما تنص", ". كما تنص")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.replace(". لكن", "، لكن")
    return dedupe_answer_text(cleaned)


def polish_english_answer_text(text: str) -> str:
    cleaned = CLAUSE_NUMBER_PATTERN.sub("", (text or "").strip())
    cleaned = cleaned.replace("Yes, The student submits", "Yes. The student submits")
    cleaned = cleaned.replace("Yes, the student submits", "Yes. The student submits")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return dedupe_answer_text(cleaned)


def build_mode_based_arabic_answer(
    question: str,
    contexts: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], bool] | None:
    mode = detect_answer_mode(question, "ar")
    if mode == "general":
        return None

    used_contexts: list[dict[str, Any]] = []
    parts: list[str] = []

    if mode == "load_limit":
        normalized_question = normalize_for_matching(question)
        asks_upper = asks_upper_limit(normalized_question)
        asks_lower = asks_lower_limit(normalized_question)
        asks_number = any(term in normalized_question for term in ("كم", "عدد", "رقم محدد", "يوجد رقم", "المسموح"))

        if asks_upper:
            definition_context = pick_context(
                contexts,
                article_terms=("الحد الاعلي للعبء الدراسي",),
                include_any=("الحد الاعلي للعبء الدراسي", "العبء الدراسي"),
            )
            practical_context = pick_context(
                contexts,
                article_terms=("العبء الدراسي",),
                include_any=("محدده من مجلس الجامعه", "يسمح للطالب التسجيل", "العبء الدراسي"),
            )
        elif asks_lower:
            definition_context = pick_context(
                contexts,
                article_terms=("الحد الادني للعبء الدراسي",),
                include_any=("الحد الادني للعبء الدراسي", "العبء الدراسي"),
            )
            practical_context = pick_context(
                contexts,
                include_any=("اقل من الحد الادني للعبء الدراسي", "لا يسمح للطالب الانسحاب"),
                article_terms=("البند 4",),
            )
        else:
            definition_context = pick_context(
                contexts,
                article_terms=("العبء الدراسي",),
                include_any=("يسمح للطالب التسجيل", "الوحدات الدراسيه", "العبء الدراسي"),
            )
            practical_context = pick_context(
                contexts,
                article_terms=("الحد الاعلي للعبء الدراسي", "الحد الادني للعبء الدراسي"),
                include_any=("العبء الدراسي", "الوحدات الدراسيه"),
            )

        if practical_context and definition_context and practical_context["id"] == definition_context["id"]:
            practical_context = None

        definition_text = extract_snippet(definition_context, question, "ar") if definition_context else ""
        practical_text = extract_snippet(practical_context, question, "ar") if practical_context else ""
        explicit_number = ""
        for candidate_text in (practical_text, definition_text):
            extracted_number_text = extract_limit_number_text(candidate_text)
            if extracted_number_text:
                explicit_number = extracted_number_text
                break

        if explicit_number:
            used_contexts.extend(
                dedupe_preserve_order_contexts(
                    [context for context in (practical_context, definition_context) if context is not None]
                )
            )
            parts.append(explicit_number)
        elif definition_text or practical_text:
            if asks_upper:
                prefix = "لم أجد في النص المتاح رقمًا محددًا للحد الأعلى للساعات، لكن اللائحة تعرفه بأنه"
            elif asks_lower:
                prefix = "لم أجد في النص المتاح رقمًا محددًا للحد الأدنى للساعات، لكن اللائحة تعرفه بأنه"
            else:
                prefix = "لم أجد في النص المتاح عددًا محددًا للساعات المسموح بها، لكن اللائحة تعرف العبء الدراسي بأنه"

            detail_parts: list[str] = []
            if definition_text:
                detail_parts.append(definition_text.rstrip(" .،"))
            normalized_practical = normalize_for_matching(practical_text)
            if practical_text and practical_text != definition_text:
                if "محدده من مجلس الجامعه" in normalized_practical:
                    detail_parts.append("ويظهر في النص أن تحديد العبء الدراسي يكون وفق ما تقرره القواعد التنفيذية أو مجلس الجامعة")
                elif asks_lower and "لا يسمح" in normalized_practical:
                    detail_parts.append("كما تنص على أنه لا يسمح بالانسحاب إذا أصبح العبء أقل من الحد الأدنى بعد تنفيذ الانسحاب")
                elif not asks_number:
                    detail_parts.append(practical_text.rstrip(" .،"))

            detail_text = "، ".join(dedupe_preserve_order(detail_parts)).strip("، ")
            if detail_text:
                parts.append(f"{prefix} {detail_text}.")
                used_contexts.extend(
                    dedupe_preserve_order_contexts(
                        [context for context in (definition_context, practical_context) if context is not None]
                    )
                )

    elif mode == "housing_conditions":
        conditions_ranked = rank_contexts_by_terms(
            contexts,
            require_all=("شروط", "اسكان"),
            include_any=("قبول", "سكن", "الطلبه", "الطلبة"),
        )
        condition_context = conditions_ranked[0] if conditions_ranked else None
        condition_text = (
            extract_matching_lines(
                condition_context,
                include_any=("الحرمان النهائي من السكن الجامعي", "غير مرتبطين بوظيفه", "استكمال", "قبول"),
                limit=1,
            )
            if condition_context
            else ""
        )

        if condition_text:
            used_contexts.append(condition_context)
            parts.append(f"من الشروط المذكورة في اللائحة: {condition_text}")

    elif mode == "lecture_recording":
        recording_ranked = rank_contexts_by_terms(
            contexts,
            require_all=("تصوير", "محاضر"),
            include_any=("موافقه", "موافقة", "تسجيل"),
            prefer_article=("المخالفات",),
        )
        recording_context = recording_ranked[0] if recording_ranked else None
        recording_text = (
            extract_matching_lines(
                recording_context,
                require_all=("تصوير", "محاضر"),
                include_any=("موافقه", "موافقة", "تسجيل"),
                limit=1,
            )
            if recording_context
            else ""
        )

        if recording_text:
            used_contexts.append(recording_context)
            if "قبل أخذ موافقة المحاضر الخطية" in recording_text:
                parts.append("لا، لا يسمح بتسجيل أو تصوير المحاضرات أو محاولة ذلك قبل أخذ موافقة المحاضر الخطية.")
            else:
                parts.append(f"لا، {recording_text}")

    elif mode == "withdrawal":
        general_ranked = rank_contexts_by_terms(
            contexts,
            include_any=("يجوز", "طلب الانسحاب", "الانسحاب من المقرر"),
            prefer_article=("الماده السابعه عشره", "المادة السابعة عشرة"),
        )
        general_context = general_ranked[0] if general_ranked else None
        restrictions = rank_contexts_by_terms(contexts, require_all=("لا يسمح", "انسحاب"))

        general_text = (
            extract_matching_lines(
                general_context,
                include_any=("يجوز", "طلب الانسحاب", "الانسحاب من المقرر"),
                limit=1,
            )
            if general_context
            else ""
        )
        restriction_texts: list[str] = []
        for context in restrictions[:2]:
            text = extract_matching_lines(context, require_all=("لا يسمح", "انسحاب"), limit=1)
            if text:
                restriction_texts.append(text)

        if general_text:
            used_contexts.append(general_context)
            parts.append("نعم، يجوز الانسحاب من المقرر وفق الضوابط التنفيذية.")
        if restriction_texts:
            used_contexts.extend(restrictions[:2])
            restriction_summary = []
            if any("الفصل الصيفي" in text for text in restriction_texts):
                restriction_summary.append("لا يسمح بالانسحاب في الفصل الصيفي")
            if any("حرمان" in text for text in restriction_texts):
                restriction_summary.append("ولا بعد الحرمان من المقرر")
            if restriction_summary:
                parts.append("لكن " + " ".join(restriction_summary) + ".")
            else:
                parts.append(f"لكن {' '.join(dedupe_preserve_order(restriction_texts))}")

    elif mode == "smoking":
        university_ranked = rank_contexts_by_terms(
            contexts,
            require_all=("تدخين", "جامعه"),
            prefer_article=("المخالفات",),
        )
        housing_ranked = rank_contexts_by_terms(contexts, include_any=("عدم التدخين", "تدخين", "الاسكان"))

        main_context = university_ranked[0] if university_ranked else None
        housing_context = next(
            (context for context in housing_ranked if "اسكان" in context_search_text(context)),
            None,
        )

        main_text = (
            extract_matching_lines(main_context, require_all=("تدخين", "جامعه"), limit=1)
            if main_context
            else ""
        )
        housing_text = (
            extract_matching_lines(housing_context, include_any=("عدم التدخين", "تدخين"), limit=1)
            if housing_context
            else ""
        )

        if main_text:
            used_contexts.append(main_context)
            parts.append(f"لا، {main_text}")
        elif housing_text:
            used_contexts.append(housing_context)
            parts.append(f"لا، {housing_text}")

        if housing_text and housing_context and housing_context not in used_contexts:
            used_contexts.append(housing_context)
            parts.append(f"كما {housing_text}")

    elif mode == "penalty":
        main_ranked = rank_contexts_by_terms(
            contexts,
            require_all=("عقوب", "غش"),
            include_any=("حرمان", "فصل", "راسب"),
            prefer_article=("العقوبات",),
        )
        example_ranked = rank_contexts_by_terms(contexts, include_any=("حرمان", "راسب", "فصل", "عقوب"))

        main_context = main_ranked[0] if main_ranked else None
        example_context = next(
            (context for context in example_ranked if context["id"] != (main_context or {}).get("id")),
            None,
        )

        main_text = (
            extract_matching_lines(main_context, include_any=("عقوبة الغش", "عقوب", "غش"), limit=1)
            if main_context
            else ""
        )
        main_text = trim_from_phrase(main_text, ("عقوبة الغش", "مع مراعاة أن تكون عقوبة الغش"))
        example_text = (
            extract_matching_lines(example_context, include_any=("حرمان", "راسب", "فصل"), limit=2)
            if example_context
            else ""
        )

        if main_text:
            used_contexts.append(main_context)
            parts.append("الغش أو محاولة الغش يعاقب بإحدى العقوبات الواردة من البند 7 إلى البند 15؛")
        if example_text:
            used_contexts.append(example_context)
            example_summary: list[str] = []
            if "الاختبار النهائي" in example_text:
                example_summary.append("ومنها الحرمان من درجة الاختبار النهائي")
            if "راسبا في المقرر" in normalize_for_matching(example_text) or "راسباً في المقرر" in example_text:
                example_summary.append("والرسوب في المقرر")
            if "الفصل النهائي" in example_text:
                example_summary.append("وقد تصل إلى الفصل النهائي من الجامعة")
            if example_summary:
                parts.append(" ".join(example_summary) + ".")
            else:
                parts.append(f"ويذكر النص المسترجع من هذه العقوبات: {example_text}")

    elif mode == "missed_final":
        absence_ranked = rank_contexts_by_terms(
            contexts,
            include_any=("غايب", "يغيب", "تغيبه", "صفر", "صفرا"),
            prefer_article=("الماده الحاديه والثلاثون", "المادة الحادية والثلاثون"),
        )
        excuse_ranked = rank_contexts_by_terms(
            contexts,
            include_any=("اختبار بديل",),
            prefer_article=("الماده الثانيه والثلاثون", "المادة الثانية والثلاثون"),
        )

        absence_context = absence_ranked[0] if absence_ranked else None
        excuse_context = excuse_ranked[0] if excuse_ranked else None

        absence_text = (
            extract_matching_lines(absence_context, include_any=("غايب", "يغيب", "صفر", "صفرا"), limit=1)
            if absence_context
            else ""
        )
        excuse_text = (
            extract_matching_lines(excuse_context, include_any=("اختبار بديل",), limit=1)
            if excuse_context
            else ""
        )

        if absence_text:
            used_contexts.append(absence_context)
            parts.append("إذا غاب الطالب عن الاختبار النهائي فتكون درجته صفراً في الاختبار.")
        if excuse_text and excuse_context and excuse_context not in used_contexts:
            used_contexts.append(excuse_context)
            parts.append("وإذا قُبل عذره فيجوز له أداء اختبار بديل.")

    used_contexts = [context for context in used_contexts if context is not None]
    if not parts or not used_contexts:
        return None

    unclear = mode == "penalty" and any(
        "[غير واضح في المصدر]" in extract_snippet(context, question, "ar")
        or context.get("metadata", {}).get("status") == "partial"
        for context in used_contexts
    )
    return " ".join(dedupe_preserve_order(parts)), dedupe_preserve_order_contexts(used_contexts), unclear


def dedupe_preserve_order_contexts(contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for context in contexts:
        if context["id"] in seen:
            continue
        seen.add(context["id"])
        deduped.append(context)
    return deduped


def build_direct_arabic_answer(question: str, snippets: list[str], unclear: bool) -> str:
    if not snippets:
        return FALLBACK_AR

    yes_no = is_yes_no_question(question, "ar")
    positive = next((snippet for snippet in snippets if any(token in snippet for token in POSITIVE_AR)), "")
    negative_snippets = [snippet for snippet in snippets if any(token in snippet for token in NEGATIVE_AR)]

    if yes_no and positive and negative_snippets:
        negative_text = " ".join(dedupe_preserve_order(negative_snippets[:2]))
        answer = f"نعم، {positive}"
        if negative_text:
            answer += f" لكن {negative_text}"
    elif yes_no and negative_snippets:
        answer = f"لا، {negative_snippets[0]}"
    elif yes_no and positive:
        answer = f"نعم، {positive}"
    else:
        answer = " ".join(dedupe_preserve_order(snippets[:2]))

    normalized_question = normalize_for_matching(question)
    if "شروط" in normalized_question and any(term in normalized_question for term in ("سكن", "اسكان")):
        if answer and not answer.startswith("من الشروط المذكورة"):
            answer = f"من الشروط المذكورة في اللائحة: {answer}"

    if unclear:
        if FALLBACK_AR in answer:
            return FALLBACK_AR
        answer = f"{answer} {UNCLEAR_AR}"
    return answer.strip()


def build_english_answer(arabic_answer: str, reference: str) -> str:
    direct_answer = translate_to_english(arabic_answer) if arabic_answer else FALLBACK_EN
    if not direct_answer:
        direct_answer = FALLBACK_EN
    direct_answer = polish_english_answer_text(direct_answer)
    if reference:
        return ENGLISH_OUTPUT_TEMPLATE.format(direct_answer=direct_answer, reference=reference).strip()
    return direct_answer


def compose_arabic_response(
    question: str,
    contexts: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], bool]:
    mode_based = build_mode_based_arabic_answer(question, contexts)
    if mode_based:
        return mode_based

    selected_contexts = select_answer_contexts(question, contexts, "ar")
    snippets = [extract_snippet(context, question, "ar") for context in selected_contexts]
    snippets = dedupe_preserve_order([snippet for snippet in snippets if snippet])

    if not snippets:
        return FALLBACK_AR, [], False

    unclear = any("[غير واضح في المصدر]" in snippet for snippet in snippets) or all(
        context.get("metadata", {}).get("status") == "partial" for context in selected_contexts
    )
    direct_answer = build_direct_arabic_answer(question, snippets, unclear)
    return direct_answer, selected_contexts, unclear


def build_arabic_answer(question: str, contexts: list[dict[str, Any]]) -> str:
    direct_answer, used_contexts, unclear = compose_arabic_response(question, contexts)
    if direct_answer == FALLBACK_AR:
        return direct_answer

    if unclear and UNCLEAR_AR not in direct_answer:
        direct_answer = f"{direct_answer} {UNCLEAR_AR}"
    answer_contexts = used_contexts if used_contexts else contexts
    direct_answer = format_arabic_direct_answer(question, direct_answer, answer_contexts)
    if is_comparison_question(question):
        direct_answer = "\n".join(dedupe_preserve_order([line for line in direct_answer.splitlines() if line.strip()]))
    else:
        direct_answer = polish_arabic_answer_text(direct_answer)

    reference = build_reference(used_contexts, "ar")
    if reference:
        return ARABIC_OUTPUT_TEMPLATE.format(direct_answer=direct_answer, reference=reference).strip()
    return direct_answer


def answer_question(question: str, top_k: int = 4) -> dict[str, Any]:
    language = detect_language(question)
    mode = detect_answer_mode(question, language) if language == "ar" else "general"
    retrieval_top_k = max(top_k, 12) if mode == "load_limit" else max(top_k, 8)
    contexts = search(question, top_k=retrieval_top_k)
    if mode == "load_limit" and language == "ar":
        contexts = dedupe_preserve_order_contexts(contexts + fallback_load_limit_contexts(question, limit=4))
    filtered_contexts = filter_contexts_for_generation(question, contexts, language)

    if not filtered_contexts:
        answer = FALLBACK_AR if language == "ar" else FALLBACK_EN
        return {
            "question": question,
            "language": language,
            "answer": answer,
            "sources": [],
        }

    direct_arabic_answer, used_contexts, unclear = compose_arabic_response(question, filtered_contexts)
    if direct_arabic_answer == FALLBACK_AR:
        answer = direct_arabic_answer if language == "ar" else FALLBACK_EN
    elif language == "ar":
        answer = build_arabic_answer(question, filtered_contexts)
    else:
        if unclear and UNCLEAR_AR not in direct_arabic_answer:
            direct_arabic_answer = f"{direct_arabic_answer} {UNCLEAR_AR}"
        direct_arabic_answer = polish_arabic_answer_text(direct_arabic_answer)
        reference = build_reference(used_contexts, "en")
        answer = build_english_answer(direct_arabic_answer, reference)

    source_contexts = used_contexts if used_contexts else filtered_contexts[:top_k]
    sources = [
        {
            "id": item["id"],
            "source": item["metadata"].get("source"),
            "document_title": item["metadata"].get("document_title"),
            "section": item["metadata"].get("section"),
            "article": item["metadata"].get("article"),
            "title": item["metadata"].get("title"),
            "score": item["score"],
            "content_preview": truncate_text(item["content"], 260),
        }
        for item in source_contexts
    ]

    return {
        "question": question,
        "language": language,
        "answer": answer,
        "sources": sources,
    }


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Ask the regulations chatbot from the command line.")
    parser.add_argument("question", help="Question in Arabic or English.")
    parser.add_argument("--top-k", type=int, default=4, help="Number of chunks to retrieve.")
    args = parser.parse_args()

    result = answer_question(args.question, top_k=args.top_k)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
