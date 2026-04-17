from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

try:
    from app.answer_item_parsing_utils import (
        LIST_ITEM_PATTERN,
        anchored_block_indices,
        build_answer_item_text,
        is_heading_like_line,
        is_rule_like_line,
        normalize_answer_item,
        strip_list_marker,
    )
    from app.answer_item_extraction_utils import (
        filter_items_for_question_kind,
        extract_context_answer_items,
        extract_snippet,
    )
    from app.chat_fallbacks import FallbackService
    from app.context_cleaning_utils import build_removable_metadata_lines, clean_context_lines
    from app.context_scoring_utils import context_answer_score, score_line
    from app.question_analysis_utils import build_question_stems, explicit_source_type_preference, infer_context_scope_hint, list_like_question_kind
    from app.record_index import iter_candidate_records
    from app.reference_utils import normalize_reference_digits as shared_normalize_reference_digits
    from app.reference_utils import parse_reference_order as shared_parse_reference_order
    from app.routing.question_router import QuestionRouter
    from app.services.answer_formatter import AnswerComputation, AnswerFormatterService, FormatterRuntimeContext
    from app.retrieve import (
        STATUS_CODE_TOKENS,
        build_display_title,
        build_query_profile,
        clean_display_section,
        detect_language,
        get_chunk_records,
        infer_record_flags,
        is_code_style_query,
        light_stem,
        normalize_for_matching,
        normalize_doc_type,
        search,
        source_priority,
        tokenize_text,
    )
    from app.translation_service import translate_text
    from app.status_code_utils import (
        STATUS_CODE_ARABIC_MEANINGS,
        STATUS_CODE_ENGLISH_MEANINGS,
        STATUS_CODE_LINE_PATTERN,
        extract_status_code_description_from_text,
        extract_status_code_meaning_from_text,
        extract_status_code_terms,
        is_status_code_query,
        select_minimal_status_code_contexts,
        status_code_context_article_matches,
    )
except ImportError:
    from answer_item_parsing_utils import (  # type: ignore
        LIST_ITEM_PATTERN,
        anchored_block_indices,
        build_answer_item_text,
        is_heading_like_line,
        is_rule_like_line,
        normalize_answer_item,
        strip_list_marker,
    )
    from answer_item_extraction_utils import (  # type: ignore
        filter_items_for_question_kind,
        extract_context_answer_items,
        extract_snippet,
    )
    from chat_fallbacks import FallbackService  # type: ignore
    from context_cleaning_utils import build_removable_metadata_lines, clean_context_lines  # type: ignore
    from context_scoring_utils import context_answer_score, score_line  # type: ignore
    from question_analysis_utils import build_question_stems, explicit_source_type_preference, infer_context_scope_hint, list_like_question_kind  # type: ignore
    from record_index import iter_candidate_records  # type: ignore
    from reference_utils import normalize_reference_digits as shared_normalize_reference_digits  # type: ignore
    from reference_utils import parse_reference_order as shared_parse_reference_order  # type: ignore
    from routing.question_router import QuestionRouter  # type: ignore
    from services.answer_formatter import AnswerComputation, AnswerFormatterService, FormatterRuntimeContext  # type: ignore
    from retrieve import (  # type: ignore
        STATUS_CODE_TOKENS,
        build_display_title,
        build_query_profile,
        clean_display_section,
        detect_language,
        get_chunk_records,
        infer_record_flags,
        is_code_style_query,
        light_stem,
        normalize_for_matching,
        normalize_doc_type,
        search,
        source_priority,
        tokenize_text,
    )
    from translation_service import translate_text  # type: ignore
    from status_code_utils import (  # type: ignore
        STATUS_CODE_ARABIC_MEANINGS,
        STATUS_CODE_ENGLISH_MEANINGS,
        STATUS_CODE_LINE_PATTERN,
        extract_status_code_description_from_text,
        extract_status_code_meaning_from_text,
        extract_status_code_terms,
        is_status_code_query,
        select_minimal_status_code_contexts,
        status_code_context_article_matches,
    )


FALLBACK_AR = "لم أجد إجابة صريحة في المصادر الجامعية المعتمدة."
FALLBACK_EN = "I could not find an explicit answer in the available university-approved sources."
UNCLEAR_AR = "المعلومات المتاحة غير واضحة في هذه النقطة."
LOW_CONFIDENCE_NOTE_AR = "\n\n⚠️ تنبيه: تعذّر إيجاد نص صريح يجيب على سؤالك بدقة عالية؛ يُنصح بمراجعة الدليل الجامعي أو الجهة المختصة للتحقق."
CONFIDENCE_HIGH_THRESHOLD = 0.72
CONFIDENCE_MED_THRESHOLD = 0.50
UNCLEAR_EN = "The retrieved text is unclear on this point."
ARABIC_GENERATION_PROMPT = """تعليمات بناء الإجابة:
- أجب مباشرة وباختصار.
- استخدم فقط النصوص المسترجعة.
- إذا لم توجد إجابة صريحة فقل: لم أجد إجابة صريحة في المصادر الجامعية المعتمدة.
- إذا كان النص غير واضح أو ناقصاً فاذكر ذلك بوضوح.
- اذكر المادة أو القسم أو اسم اللائحة عند الإمكان.
"""
ENGLISH_GENERATION_PROMPT = """Answering rules:
- Answer directly and briefly.
- Use only the retrieved university-approved source text.
- If no explicit answer is found, say so clearly.
- If the retrieved text is unclear, say that it is unclear.
- Mention the article, section, or source when helpful.
"""
ARABIC_OUTPUT_TEMPLATE = "{direct_answer}\nالمصدر المعتمد: {reference}"
ENGLISH_OUTPUT_TEMPLATE = "{direct_answer}\nOfficial source: {reference}"
YES_NO_PATTERN_EN = re.compile(r"^(can|is|are|do|does|did|will|may|should)\b", re.IGNORECASE)
POSITIVE_AR = ("يجوز", "يسمح", "يحق")
NEGATIVE_AR = ("لا يسمح", "لا يجوز", "عدم", "محظور", "ممنوع")
CLAUSE_NUMBER_PATTERN = re.compile(r"(?<!\d)\b[\d٠-٩]+\.\s+")
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[\.\!\؟])\s+|\n+")
NUMBER_PATTERN = re.compile(r"[\d٠-٩]+")
MIN_ARABIC_TOP_SCORE = 0.34
SOURCE_TYPE_LABELS_AR = {
    "regulation": "لائحة",
    "policy": "سياسة",
    "guide": "دليل",
    "faq": "أسئلة شائعة",
}
SOURCE_TYPE_LABELS_EN = {
    "regulation": "Regulation",
    "policy": "Policy",
    "guide": "Guide",
    "faq": "FAQ",
}
STRICT_ROUTE_MODES = {
    "attendance_penalty",
    "housing_conditions",
    "lecture_recording",
    "missed_final",
    "penalty",
    "withdrawal",
}
COVERAGE_CATEGORY_RULES: dict[str, dict[str, tuple[str, ...] | str]] = {
    "financial": {
        "query_terms": ("قرض", "مكاف", "اعان", "منح", "رسوم", "تمويل", "financial", "loan", "scholarship"),
        "label_ar": "التمويل والمنح",
        "label_en": "financial support",
    },
    "facilities": {
        "query_terms": ("مرافق", "منشات", "نادي", "رياض", "ملعب", "مختبر", "مكتبه", "facilities", "sports"),
        "label_ar": "المرافق والخدمات",
        "label_en": "campus facilities",
    },
    "dress": {
        "query_terms": ("زي", "مظهر", "لبس", "عباي", "dress", "uniform"),
        "label_ar": "الزي الجامعي",
        "label_en": "dress code",
    },
}


logger = logging.getLogger(__name__)


fallback_service = FallbackService()
question_router = QuestionRouter(fallback_service=fallback_service)
formatter = AnswerFormatterService()


@dataclass(frozen=True, slots=True)
class RouteDecision:
    mode: str
    fallback_mode: str | None
    uses_fallback_flow: bool
    retrieval_top_k: int
    is_attendance_limit: bool

    @classmethod
    def from_mapping(cls, route: dict[str, Any], *, retrieval_top_k: int, is_attendance_limit: bool) -> RouteDecision:
        return cls(
            mode=str(route["mode"]),
            fallback_mode=route.get("fallback_mode"),
            uses_fallback_flow=bool(route.get("uses_fallback_flow")),
            retrieval_top_k=retrieval_top_k,
            is_attendance_limit=is_attendance_limit,
        )


def mode_requires_strict_context_match(mode: str) -> bool:
    return mode in STRICT_ROUTE_MODES


def compute_answer_confidence(contexts: list[dict[str, Any]]) -> tuple[str, float]:
    """Return a (level, score) tuple describing retrieval confidence.

    Levels:
      "high"   – top retrieval score >= CONFIDENCE_HIGH_THRESHOLD
      "medium" – top retrieval score >= CONFIDENCE_MED_THRESHOLD
      "low"    – top retrieval score below CONFIDENCE_MED_THRESHOLD or no contexts
    """
    if not contexts:
        return "low", 0.0
    top_score = max(float(c.get("score", 0.0)) for c in contexts)
    if top_score >= CONFIDENCE_HIGH_THRESHOLD:
        return "high", top_score
    if top_score >= CONFIDENCE_MED_THRESHOLD:
        return "medium", top_score
    return "low", top_score


def detect_coverage_category(question: str) -> str | None:
    normalized_question = normalize_for_matching(question)
    for category, rule in COVERAGE_CATEGORY_RULES.items():
        query_terms = rule.get("query_terms", ())
        if any(term in normalized_question for term in query_terms):
            return category
    return None


def context_matches_coverage_category(context: dict[str, Any], category: str) -> bool:
    record_flags = infer_record_flags(context)
    return bool(record_flags.get(category, False))


def assess_category_source_coverage(question: str, contexts: list[dict[str, Any]]) -> dict[str, Any] | None:
    category = detect_coverage_category(question)
    if not category:
        return None

    category_contexts = [context for context in contexts if context_matches_coverage_category(context, category)]
    min_score = 0.34 if category == "dress" else CONFIDENCE_MED_THRESHOLD
    strong_contexts = [
        context
        for context in category_contexts
        if not context_is_weak(context) and float(context.get("score", 0.0)) >= min_score
    ]
    return {
        "category": category,
        "matched_contexts": len(category_contexts),
        "strong_contexts": len(strong_contexts),
        "has_gap": len(strong_contexts) == 0,
    }


def build_coverage_gap_fallback(language: str, category: str) -> str:
    category_rule = COVERAGE_CATEGORY_RULES.get(category, {})
    label_ar = str(category_rule.get("label_ar", "هذا الموضوع"))
    label_en = str(category_rule.get("label_en", "this topic"))
    if language == "ar":
        return (
            f"لا تتوفر في المصادر الجامعية المعتمدة الحالية تغطية كافية لموضوع {label_ar}؛ "
            "لذلك لا أستطيع تقديم إجابة دقيقة الآن."
        )
    return (
        f"The currently approved university sources do not provide enough coverage for {label_en}, "
        "so I cannot provide a reliable answer yet."
    )


def context_matches_route_mode(context: dict[str, Any], mode: str) -> bool:
    if not mode_requires_strict_context_match(mode):
        return True

    haystack = context_search_text(context)
    record_flags = infer_record_flags(context)

    if mode == "lecture_recording":
        has_recording_action = any(term in haystack for term in ("تصوير", "تسجيل"))
        has_lecture_anchor = any(term in haystack for term in ("محاضر", "محاضره", "محاضرات"))
        has_permission_anchor = any(term in haystack for term in ("موافقه", "الخطيه", "قبل اخذ"))
        return record_flags["lecture_recording"] or (
            has_recording_action and has_lecture_anchor and has_permission_anchor
        )

    if mode == "withdrawal":
        return record_flags["withdrawal"] or any(
            term in haystack
            for term in (
                "الانسحاب من مقرر",
                "الانسحاب من المقرر",
                "يجوز للطالب الانسحاب",
                "طلب الانسحاب",
            )
        )

    if mode == "missed_final":
        return record_flags["missed_final"] or (
            any(term in haystack for term in ("الاختبار النهايي", "الاختبار النهائي", "اختبار بديل"))
            and any(term in haystack for term in ("غاب", "غايب", "يغيب", "صفر", "صفرا", "عذر"))
        )

    if mode == "penalty":
        return ("غش" in haystack) and any(
            term in haystack
            for term in (
                "عقوب",
                "الماده الثامنه",
                "المادة الثامنة",
                "راسب",
                "فصل",
                "حرمان",
            )
        )

    if mode == "housing_conditions":
        # Keep matching tight: only accept contexts explicitly about housing admission/eligibility.
        normalized = normalize_for_matching(context_search_text(context))
        has_housing_anchor = any(term in normalized for term in ("السكن", "الاسكان", "الاسكان الطلابي", "الاقامه بالسكن", "الاقامة بالسكن"))
        if not has_housing_anchor:
            return False
        if "ضوابط الدخول والخروج" in normalized:
            return False
        if not any(term in normalized for term in ("شروط القبول", "قبول", "يشترط", "متطلبات", "استحقاق", "اهليه")):
            return False
        if any(term in normalized for term in ("حرمان", "عقوب", "مخالف", "طرد", "اخلاء", "نهائي", "منع", "ممنوع")):
            return False
        return True

    if mode == "attendance_penalty":
        return (
            record_flags["attendance"]
            and any(term in haystack for term in ("حرمان", "الحضور", "الاختبار النهائي"))
            and not any(term in haystack for term in ("غش", "انسحاب", "سكن", "اسكان"))
        )

    return True


def filter_contexts_by_route_mode(contexts: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    if not mode_requires_strict_context_match(mode):
        return contexts[:]
    return [context for context in contexts if context_matches_route_mode(context, mode)]


def build_context_diagnostic_entry(context: dict[str, Any], *, route_mode: str | None = None) -> dict[str, Any]:
    metadata = context.get("metadata", {})
    preview = re.sub(r"\s+", " ", str(context.get("content", ""))).strip()
    entry = {
        "id": context.get("id", ""),
        "score": round(float(context.get("score", 0.0)), 4),
        "lexical_score": round(float(context.get("lexical_score", 0.0)), 4),
        "semantic_score": round(float(context.get("semantic_score", 0.0)), 4),
        "document_title": metadata.get("document_title", ""),
        "article": metadata.get("article", ""),
        "section": metadata.get("section", ""),
        "content_preview": truncate_text(preview, 180),
    }
    if route_mode is not None and mode_requires_strict_context_match(route_mode):
        entry["mode_match"] = context_matches_route_mode(context, route_mode)
    return entry


def emit_chat_diagnostics(
    *,
    stage: str,
    original_question: str,
    working_question: str,
    normalized_query: str,
    language: str,
    route: RouteDecision,
    retrieved_contexts: list[dict[str, Any]] | None = None,
    filtered_contexts: list[dict[str, Any]] | None = None,
    source_contexts: list[dict[str, Any]] | None = None,
    fallback_reason: str | None = None,
    answer: str | None = None,
) -> None:
    payload: dict[str, Any] = {
        "stage": stage,
        "original_question_len": len((original_question or "").strip()),
        "working_question_len": len((working_question or "").strip()),
        "normalized_query_len": len((normalized_query or "").strip()),
        "language": language,
        "route": {
            "mode": route.mode,
            "fallback_mode": route.fallback_mode,
            "uses_fallback_flow": route.uses_fallback_flow,
            "retrieval_top_k": route.retrieval_top_k,
            "is_attendance_limit": route.is_attendance_limit,
        },
    }

    if retrieved_contexts is not None:
        payload["retrieved_contexts"] = [
            build_context_diagnostic_entry(context, route_mode=route.mode)
            for context in retrieved_contexts[:6]
        ]
    if filtered_contexts is not None:
        payload["filtered_contexts"] = [
            build_context_diagnostic_entry(context, route_mode=route.mode)
            for context in filtered_contexts[:6]
        ]
    if source_contexts is not None:
        payload["final_citations"] = [
            build_context_diagnostic_entry(context, route_mode=route.mode)
            for context in source_contexts[:6]
        ]
    if fallback_reason:
        payload["fallback_reason"] = fallback_reason
    if answer:
        payload["answer_len"] = len(answer.strip())

    logger.info("chat_diagnostics %s", json.dumps(payload, ensure_ascii=False))


def _formatter_context() -> FormatterRuntimeContext:
    return FormatterRuntimeContext(
        fallback_ar=FALLBACK_AR,
        fallback_en=FALLBACK_EN,
        unclear_ar=UNCLEAR_AR,
        arabic_output_template=ARABIC_OUTPUT_TEMPLATE,
        english_output_template=ENGLISH_OUTPUT_TEMPLATE,
        translate_to_english=translate_to_english,
        polish_english_answer_text=polish_english_answer_text,
        normalize_english_status_code_meanings=normalize_english_status_code_meanings,
        context_source_type=context_source_type,
        clean_display_section=clean_display_section,
        build_display_title=build_display_title,
        normalize_for_matching=normalize_for_matching,
        source_reference_tag=source_reference_tag,
        context_is_partial=context_is_partial,
        source_priority=source_priority,
        parse_reference_order=parse_reference_order,
        extract_status_code_terms=extract_status_code_terms,
        extract_context_answer_items=extract_context_answer_items,
        append_uncertainty_note=append_uncertainty_note,
        clean_supporting_source_snippet=clean_supporting_source_snippet,
        extract_snippet=extract_snippet,
        uncertainty_note=uncertainty_note,
        list_like_question_kind=list_like_question_kind,
        dedupe_preserve_order=dedupe_preserve_order,
        compose_arabic_response=compose_arabic_response,
        should_prefer_extractive_answer=should_prefer_extractive_answer,
        format_arabic_direct_answer=format_arabic_direct_answer,
        select_evidence_contexts=select_evidence_contexts,
        build_status_code_arabic_answer=build_status_code_arabic_answer,
        build_attendance_limit_arabic_answer=build_attendance_limit_arabic_answer,
        detect_answer_mode=detect_answer_mode,
        build_list_like_arabic_answer=build_list_like_arabic_answer,
        is_attendance_limit_question=is_attendance_limit_question,
        is_comparison_question=is_comparison_question,
        polish_multiline_arabic_answer_text=polish_multiline_arabic_answer_text,
        polish_arabic_answer_text=polish_arabic_answer_text,
        contexts_have_quality_risk=contexts_have_quality_risk,
        apply_source_aware_arabic_wording=apply_source_aware_arabic_wording,
        append_secondary_source_clarification=append_secondary_source_clarification,
        maybe_format_arabic_list_answer=maybe_format_arabic_list_answer,
        normalize_doc_type=normalize_doc_type,
    )


def truncate_text(text: str, limit: int = 700) -> str:
    return formatter.truncate_text(text, limit)


def asks_upper_limit(normalized_question: str) -> bool:
    return fallback_service.asks_upper_limit(normalized_question)


def asks_lower_limit(normalized_question: str) -> bool:
    return fallback_service.asks_lower_limit(normalized_question)


def context_search_text(context: dict[str, Any]) -> str:
    return fallback_service.context_search_text(context)


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


def translate_to_english(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""
    try:
        result = translate_text(cleaned)
        return result["translated_text"]
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

    deduped_text = " ".join(deduped_sentences).strip()
    repeated_clause_parts = [part.strip(" ،.") for part in re.split(r"\s+لكن\s+", deduped_text) if part.strip(" ،.")]
    if len(repeated_clause_parts) > 1:
        deduped_parts = dedupe_preserve_order(repeated_clause_parts)
        deduped_text = " لكن ".join(deduped_parts).strip()

    return deduped_text


def rewrite_query(question: str) -> str:
    cleaned = (question or "").strip()
    if not cleaned or detect_language(cleaned) != "ar":
        return cleaned

    normalized = normalize_for_matching(cleaned)
    rewritten_parts = [cleaned]
    seen = {normalize_for_matching(cleaned)}

    def add_rewrite(text: str) -> None:
        normalized_text = normalize_for_matching(text)
        if normalized_text and normalized_text not in seen:
            seen.add(normalized_text)
            rewritten_parts.append(text)

    if any(term in normalized for term in ("انسحب", "انسحاب", "سحب", "حذف", "احذف", "اسحب")):
        add_rewrite("انسحاب من مقرر")

    if any(phrase in normalized for phrase in ("وش يصير", "ايش يصير", "شو يصير", "وش الحكم", "وش النتيجه")):
        add_rewrite("ما النتائج")
        add_rewrite("ما الحكم")

    if any(phrase in normalized for phrase in ("بدون اذن", "دون اذن", "بلا اذن")):
        add_rewrite("دون موافقة")
        add_rewrite("قبل أخذ موافقة")

    if (
        any(term in normalized for term in ("غبت", "غاب", "فاتني", "يغيب", "غياب"))
        and any(term in normalized for term in ("نهائي", "النهايي", "النهائي"))
    ):
        add_rewrite("الغياب عن الاختبار النهائي")

    if "تصوير" in normalized and any(term in normalized for term in ("محاضره", "محاضرات", "المحاضره", "المحاضرات")):
        add_rewrite("تصوير المحاضرات")
    if any(term in normalized for term in ("اصور", "أصور", "تصوير")) and any(
        phrase in normalized for phrase in ("بدون اذن", "دون اذن", "بلا اذن", "بدون موافقه", "دون موافقه")
    ):
        add_rewrite("تصوير المحاضرات")
        add_rewrite("التصوير دون موافقة")
        add_rewrite("قبل أخذ موافقة")
    if "تصوير" in normalized and any(phrase in normalized for phrase in ("بدون اذن", "دون اذن", "بلا اذن", "دون موافقه", "بدون موافقه")):
        add_rewrite("تصوير المحاضرات دون موافقة")

    if any(term in normalized for term in ("بعذر", "بعذر؟", "بعذر.", "عذر", "عذره")):
        add_rewrite("إذا قُبل العذر")
        if any(term in normalized for term in ("غبت", "غاب", "فاتني", "نهائي", "النهائي", "النهايي")):
            add_rewrite("اختبار بديل")

    if "حرمان" in normalized and "اختبار" in normalized and any(term in normalized for term in ("نهائي", "النهايي", "النهائي")):
        add_rewrite("الحرمان من الاختبار النهائي")

    if ("حرمان" in normalized and "كم" in normalized) or (
        "حرمان" in normalized and any(term in normalized for term in ("علاقه", "علاقة")) and "اختبار" in normalized
    ):
        add_rewrite("ما نسبة الحضور المطلوبة")
        add_rewrite("العلاقة بين الحرمان والاختبار النهائي")
        add_rewrite("نسبة الحضور")
        add_rewrite("الحرمان من الاختبار النهائي")
        add_rewrite("دخول الاختبار النهائي")

    return " ".join(part for part in rewritten_parts if part).strip()


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


def context_source_type(context: dict[str, Any]) -> str:
    return normalize_doc_type(context.get("metadata", {}).get("doc_type", "regulation"))


def source_type_label(doc_type: str, language: str) -> str:
    normalized = normalize_doc_type(doc_type)
    if language == "ar":
        return SOURCE_TYPE_LABELS_AR.get(normalized, SOURCE_TYPE_LABELS_AR["regulation"])
    return SOURCE_TYPE_LABELS_EN.get(normalized, SOURCE_TYPE_LABELS_EN["regulation"])


def source_reference_tag(doc_type: str, language: str) -> str:
    return f"[{source_type_label(doc_type, language)}]"


def context_qa_flags(context: dict[str, Any]) -> set[str]:
    return {
        flag
        for flag in context.get("metadata", {}).get("qa_flags", [])
        if isinstance(flag, str)
    }


def context_is_partial(context: dict[str, Any]) -> bool:
    metadata = context.get("metadata", {})
    return metadata.get("status") == "partial" or "partial_chunk" in context_qa_flags(context)


def context_is_low_signal(context: dict[str, Any]) -> bool:
    return bool({"low_signal_chunk", "heading_only_chunk", "tiny_chunk"} & context_qa_flags(context))


def contexts_have_quality_risk(contexts: list[dict[str, Any]]) -> bool:
    return any(context_is_partial(context) or context_is_low_signal(context) for context in contexts)


def context_word_count(context: dict[str, Any]) -> int:
    return len([token for token in context.get("content", "").split() if token.strip()])


def context_is_weak(context: dict[str, Any]) -> bool:
    return context_is_partial(context) or context_is_low_signal(context) or context_word_count(context) < 12


def filter_weak_contexts(contexts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    strong_contexts = [context for context in contexts if not context_is_weak(context)]
    return strong_contexts if strong_contexts else contexts


def uncertainty_note(language: str) -> str:
    return UNCLEAR_AR if language == "ar" else UNCLEAR_EN


def append_uncertainty_note(text: str, language: str) -> str:
    cleaned = (text or "").strip()
    note = uncertainty_note(language)
    if not cleaned:
        return note
    if note in cleaned:
        return cleaned
    return f"{cleaned} {note}".strip()


def should_prefer_extractive_answer(
    question: str,
    contexts: list[dict[str, Any]],
    *,
    unclear: bool,
) -> bool:
    if is_status_code_query(question):
        return False
    if is_attendance_limit_question(question):
        return False
    if unclear or contexts_have_quality_risk(contexts):
        return True
    return detect_answer_mode(question, "ar") in {
        "general",
        "attendance_penalty",
        "smoking",
    }


def source_intro_phrase(doc_type: str, language: str, *, secondary: bool = False) -> str:
    normalized = normalize_doc_type(doc_type)
    if language == "ar":
        if secondary:
            return {
                "regulation": "كما ورد في اللائحة، ",
                "policy": "كما ورد في السياسة، ",
                "guide": "وفي الدليل ورد: ",
                "faq": "وفي الأسئلة الشائعة ورد: ",
            }.get(normalized, "كما ورد في اللائحة، ")
        return {
            "regulation": "وفق اللائحة، ",
            "policy": "وفق السياسة، ",
            "guide": "وفق الدليل، ",
            "faq": "وفق الأسئلة الشائعة، ",
        }.get(normalized, "وفق اللائحة، ")
    if secondary:
        return {
            "regulation": "And according to the regulation, ",
            "policy": "And according to the policy, ",
            "guide": "And the guide states: ",
            "faq": "And the FAQ states: ",
        }.get(normalized, "And according to the regulation, ")
    return {
        "regulation": "According to the regulation, ",
        "policy": "According to the policy, ",
        "guide": "According to the guide, ",
        "faq": "According to the FAQ, ",
    }.get(normalized, "According to the regulation, ")


def primary_source_context(contexts: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not contexts:
        return None
    return max(
        contexts,
        key=lambda context: (
            source_priority(context_source_type(context)),
            float(context.get("score", 0.0)),
            float(context.get("lexical_score", 0.0)),
            float(context.get("semantic_score", 0.0)),
        ),
    )


def clean_supporting_source_snippet(snippet: str) -> str:
    cleaned = polish_arabic_answer_text(snippet)
    cleaned = limit_answer_sentences(cleaned, max_sentences=2)
    return cleaned.strip()


def pick_embedded_secondary_context(
    contexts: list[dict[str, Any]],
    primary_context: dict[str, Any] | None,
    *,
    exclude_ids: set[str] | None = None,
) -> dict[str, Any] | None:
    if primary_context is None:
        return None

    excluded = exclude_ids or set()
    primary_priority = source_priority(context_source_type(primary_context))
    if primary_priority <= 0:
        return None

    secondary_candidates = [
        context
        for context in contexts
        if context["id"] not in excluded
        and source_priority(context_source_type(context)) < primary_priority
    ]
    if not secondary_candidates:
        return None

    return max(
        secondary_candidates,
        key=lambda context: (
            source_priority(context_source_type(context)),
            float(context.get("score", 0.0)),
            float(context.get("lexical_score", 0.0)),
            float(context.get("semantic_score", 0.0)),
        ),
    )


def append_secondary_source_clarification(
    question: str,
    answer: str,
    contexts: list[dict[str, Any]],
) -> str:
    cleaned_answer = (answer or "").strip()
    if not cleaned_answer or cleaned_answer == FALLBACK_AR or is_comparison_question(question):
        return cleaned_answer

    primary_context = primary_source_context(contexts)
    secondary_context = pick_embedded_secondary_context(
        contexts,
        primary_context,
        exclude_ids={primary_context["id"]} if primary_context else None,
    )
    if secondary_context is None:
        return cleaned_answer

    snippet = clean_supporting_source_snippet(extract_snippet(secondary_context, question, "ar"))
    snippet = strip_leading_connector(snippet).rstrip(" .،")
    if not snippet:
        return cleaned_answer

    normalized_answer = normalize_for_matching(cleaned_answer)
    normalized_snippet = normalize_for_matching(snippet)
    if normalized_snippet and normalized_snippet in normalized_answer:
        return cleaned_answer

    clarification = f"{source_intro_phrase(context_source_type(secondary_context), 'ar', secondary=True)}{snippet}."
    return dedupe_answer_text(f"{cleaned_answer} {clarification}".strip())


def strip_leading_connector(text: str) -> str:
    return re.sub(r"^(لكن|كما|وإذا|واذا)\s+", "", (text or "").strip())


def penalty_question_domain(question: str) -> str | None:
    return question_router.penalty_question_domain(question)


def is_gpa_formula_question(question: str) -> bool:
    return question_router.is_gpa_formula_question(question)


def is_admission_conditions_question(question: str) -> bool:
    return question_router.is_admission_conditions_question(question)


def list_like_intro(question: str, *, item_count: int, contexts: list[dict[str, Any]] | None = None) -> str:
    kind = list_like_question_kind(question)
    normalized_question = normalize_for_matching(question)
    if is_admission_conditions_question(question):
        has_admission_guide = any(
            "دليل القبول الجامعي" in (context.get("metadata", {}).get("document_title", "") or "")
            for context in (contexts or [])
        )
        has_program_specific_section = any(
            any(
                marker in normalize_for_matching(context.get("metadata", {}).get("section", ""))
                for marker in ("دبلوم", "برنامج", "بكالوريوس", "كليه", "كلية")
            )
            for context in (contexts or [])
        )
        if has_admission_guide and has_program_specific_section:
            return "من الشروط التي ظهرت في النص المتاح من دليل القبول الجامعي لبرامج الجامعة، وقد تختلف بعض التفاصيل بحسب البرنامج"
        if has_admission_guide:
            return "من الشروط التي وردت في دليل القبول الجامعي"

    if kind == "penalties" and penalty_question_domain(question) == "cheating":
        return "من العقوبات المذكورة للغش أو محاولته وفق اللائحة"

    partial_intro = {
        "conditions": "من الشروط التي وردت في اللائحة",
        "rules": "من الضوابط المذكورة في اللائحة",
        "steps": "من الخطوات المذكورة في اللائحة",
        "penalties": "من العقوبات المذكورة في اللائحة",
        "cases": "من الحالات المذكورة في اللائحة",
        "policy": "من الضوابط التي وردت في اللائحة",
        "system": "من التقديرات المذكورة في اللائحة"
        if "تقدير" in normalized_question
        else "من البنود المذكورة في اللائحة",
    }.get(kind, "وفق اللائحة، ورد")
    scope_hint = infer_context_scope_hint(question, contexts or [])
    if scope_hint:
        return f"{partial_intro} {scope_hint}".strip()
    return partial_intro


def status_code_context_exact_matches(context: dict[str, Any], codes: list[str]) -> set[str]:
    haystack = f" {context_search_text(context)} "
    return {code for code in codes if f" {code} " in haystack}


def status_code_context_definition_matches(context: dict[str, Any], codes: list[str]) -> set[str]:
    matched: set[str] = set()
    for line in clean_context_lines(context):
        tokens = tokenize_text(line)
        if not tokens:
            continue
        first_token = tokens[0]
        for code in codes:
            if code not in matched and first_token == code:
                matched.add(code)
    return matched


def status_code_source_key(context: dict[str, Any]) -> tuple[str, str]:
    metadata = context.get("metadata", {})
    source_title = normalize_for_matching(
        metadata.get("document_title", "")
        or metadata.get("source", "")
        or build_display_title(
            document_title=metadata.get("document_title", ""),
            article=metadata.get("article", ""),
            section=metadata.get("section", ""),
            fallback_title=metadata.get("title", ""),
        )
    )
    return (context_source_type(context), source_title)


def status_code_context_details(context: dict[str, Any], codes: list[str]) -> dict[str, Any]:
    exact_matches = status_code_context_exact_matches(context, codes)
    article_matches = status_code_context_article_matches(context, codes)
    definition_matches = status_code_context_definition_matches(context, codes)
    doc_type = context_source_type(context)
    coverage_count = len(exact_matches)
    definition_count = len(definition_matches)
    article_count = len(article_matches)

    score = (
        (float(context.get("score", 0.0)) * 1.2)
        + (float(context.get("lexical_score", 0.0)) * 1.5)
        + (float(context.get("semantic_score", context.get("score", 0.0))) * 0.7)
        + (coverage_count * 1.7)
        + (definition_count * 1.2)
        + (article_count * 0.8)
        + (source_priority(doc_type) * 0.2)
    )
    if len(codes) > 1 and coverage_count == len(codes):
        score += 1.1
    if definition_count == len(codes):
        score += 0.9

    return {
        "context": context,
        "exact_matches": exact_matches,
        "article_matches": article_matches,
        "definition_matches": definition_matches,
        "coverage_count": coverage_count,
        "definition_count": definition_count,
        "source_priority": source_priority(doc_type),
        "selection_score": score,
        "source_key": status_code_source_key(context),
    }


def select_status_code_contexts(
    question: str,
    contexts: list[dict[str, Any]],
    *,
    max_items: int,
) -> list[dict[str, Any]]:
    codes = extract_status_code_terms(question)
    if not codes or not is_status_code_query(question):
        return []

    deduped_contexts = dedupe_preserve_order_contexts(contexts)
    detailed_contexts = [
        status_code_context_details(context, codes)
        for context in deduped_contexts
    ]
    detailed_contexts = [details for details in detailed_contexts if details["coverage_count"] > 0]
    if not detailed_contexts:
        return []

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for details in detailed_contexts:
        grouped.setdefault(details["source_key"], []).append(details)

    group_summaries: list[dict[str, Any]] = []
    for group_details in grouped.values():
        ordered_details = sorted(
            group_details,
            key=lambda item: (
                item["selection_score"],
                item["definition_count"],
                item["coverage_count"],
            ),
            reverse=True,
        )
        selected_contexts, covered_codes, definition_coverage_count = select_minimal_status_code_contexts(
            ordered_details,
            codes,
            max_items=max_items,
        )
        if not selected_contexts:
            continue

        group_summaries.append(
            {
                "source_key": ordered_details[0]["source_key"],
                "contexts": selected_contexts,
                "covered_count": len(covered_codes),
                "definition_coverage_count": definition_coverage_count,
                "source_priority": max(item["source_priority"] for item in ordered_details),
                "best_context_score": ordered_details[0]["selection_score"],
                "context_count": len(selected_contexts),
                "has_single_context_full_coverage": int(
                    any(item["coverage_count"] == len(codes) for item in ordered_details)
                ),
            }
        )

    if not group_summaries:
        return []

    full_coverage_groups = [summary for summary in group_summaries if summary["covered_count"] == len(codes)]
    if full_coverage_groups:
        best_group = max(
            full_coverage_groups,
            key=lambda item: (
                item["has_single_context_full_coverage"],
                item["definition_coverage_count"],
                item["source_priority"],
                -item["context_count"],
                item["best_context_score"],
            ),
        )
        return dedupe_preserve_order_contexts(best_group["contexts"])[:max_items]

    selected_groups: list[dict[str, Any]] = []
    covered_codes: set[str] = set()
    for summary in sorted(
        group_summaries,
        key=lambda item: (
            item["source_priority"],
            item["definition_coverage_count"],
            item["covered_count"],
            -item["context_count"],
            item["best_context_score"],
        ),
        reverse=True,
    ):
        summary_codes = set()
        for context in summary["contexts"]:
            summary_codes |= status_code_context_exact_matches(context, codes)
        new_codes = summary_codes - covered_codes
        if not new_codes and selected_groups:
            continue

        selected_groups.append(summary)
        covered_codes |= summary_codes
        if covered_codes >= set(codes) or len(selected_groups) >= max_items:
            break

    flattened_contexts: list[dict[str, Any]] = []
    for summary in selected_groups:
        flattened_contexts.extend(summary["contexts"])
    return dedupe_preserve_order_contexts(flattened_contexts)[:max_items]


def build_query_profile_for_answer(question: str, language: str) -> dict[str, Any]:
    if language == "ar":
        profile = build_query_profile(question)
        normalized_question = profile["normalized_query"]
        extra_stems: list[str] = []

        if any(term in normalized_question for term in ("غبت", "غاب", "غايب", "يغيب")):
            extra_stems.extend(["غيب", "حضور", "حرمان"])
        if any(term in normalized_question for term in ("غياب", "حضور", "حرمان")) and "نسب" in normalized_question:
            extra_stems.extend(["غيب", "حضور", "حرمان"])
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

    mode = detect_answer_mode(question, language)
    if mode_requires_strict_context_match(mode) and not context_matches_route_mode(context, mode):
        return False

    # For housing admission/eligibility questions, strict mode matching is enough.
    # Lexical "important stems" can miss synonyms (e.g. سكن vs إسكان) in the source text.
    if language == "ar" and mode == "housing_conditions":
        return True

    if details["phrase_matches"] > 0:
        return True

    # Broad general questions can be grounded by strong semantic matches even
    # when lexical overlap is low, such as asking generally about university regulations.
    if (
        mode == "general"
        and not query_profile["important_stems"]
        and len(query_profile["tokens"]) >= 2
        and details["semantic_score"] >= 0.7
        and (
            details["token_matches"] > 0
            or details["metadata_hits"] > 0
            or details["stem_matches"] > 0
        )
    ):
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


def augment_contexts_for_route(
    question: str,
    contexts: list[dict[str, Any]],
    language: str,
    *,
    route: RouteDecision,
    fallback_service: FallbackService,
) -> list[dict[str, Any]]:
    if language != "ar" or not contexts:
        return contexts

    augmented = dedupe_preserve_order_contexts(contexts)
    mode = route.mode

    def add_fallback(mode: str, *, limit: int, include_question: bool = False) -> None:
        nonlocal augmented
        fallback_contexts = fallback_service.get_fallback_context(
            mode,
            question=question if include_question else None,
            limit=limit,
        )
        if fallback_contexts:
            augmented = dedupe_preserve_order_contexts(augmented + fallback_contexts)

    if route.mode == "withdrawal":
        add_fallback("withdrawal", limit=4)
    elif route.mode == "missed_final":
        add_fallback("missed_final", limit=4)
    elif route.mode == "lecture_recording":
        add_fallback("lecture_recording", limit=2)
    elif route.mode == "load_limit":
        add_fallback("load_limit", limit=4, include_question=True)
    elif route.mode == "housing_conditions":
        add_fallback("housing_conditions", limit=4)
    elif route.mode == "penalty":
        add_fallback("penalty", limit=4)

    # Use augmented contexts (retrieval + curated fallbacks) for scoring/gating below.
    contexts = augmented

    if mode == "housing_conditions":
        # Keep only admission/eligibility contexts for housing conditions.
        deny_terms = ("حرمان", "عقوب", "مخالف", "طرد", "اخلاء", "نهائي", "منع", "ممنوع")
        contexts = [
            context
            for context in contexts
            if "القواعد المنظمه للاسكان الطلابي" in context_search_text(context)
            and "شروط القبول" in context_search_text(context)
            and "ضوابط الدخول والخروج" not in context_search_text(context)
            and not any(term in context_search_text(context) for term in deny_terms)
        ] or contexts


    if mode == "missed_final":
        mode_contexts = rank_contexts_by_terms(
            contexts,
            include_any=("غبت", "غاب", "غايب", "يغيب", "صفر", "اختبار بديل"),
            prefer_article=("المادة الحادية والثلاثون", "المادة الثانية والثلاثون"),
        )[:3]
        if mode_contexts:
            return dedupe_preserve_order_contexts(mode_contexts)
    if mode == "penalty":
        fallback_penalty_contexts = fallback_service.get_fallback_context("penalty", limit=3)
        if fallback_penalty_contexts:
            return dedupe_preserve_order_contexts(fallback_penalty_contexts)
        penalty_pool = [
            context
            for context in contexts
            if any(term in context_search_text(context) for term in ("الغش", "العقوبات", "حرمان", "راسب", "فصل"))
            and "المادة الخامسة" not in context_search_text(context)
        ]
        direct_penalty_contexts = [
            context
            for context in penalty_pool
            if "الماده الثامنه" in context_search_text(context)
            and any(
                term in context_search_text(context)
                for term in (
                    "الاختبار الدوري",
                    "الاختبار النصفي",
                    "الاختبار النهايي",
                    "راسب",
                    "الفصل من الجامعه",
                    "الفصل النهايي من الجامعه",
                )
            )
        ]
        if direct_penalty_contexts:
            mode_contexts = [
                context
                for context in rank_contexts_by_terms(
                    direct_penalty_contexts,
                    include_any=("الاختبار النهايي", "الاختبار الدوري", "الاختبار النصفي", "راسب", "المقرر", "فصل", "حرمان"),
                    prefer_article=("الماده الثامنه",),
                )
            ][:3]
        else:
            mode_contexts = [
                context
                for context in rank_contexts_by_terms(
                    penalty_pool or contexts,
                    include_any=("الغش", "العقوبات", "الاختبار النهائي", "راسب", "فصل", "حرمان"),
                    prefer_article=("المادة الثامنة", "الإجراءات المتبعة في حالة الغش"),
                )
            ][:3]
        if mode_contexts:
            return dedupe_preserve_order_contexts(mode_contexts)
    if mode == "lecture_recording":
        # Strict: reject contexts that only mention lectures/schedules but not recording.
        recording_contexts: list[dict[str, Any]] = []
        for context in contexts:
            text = normalize_for_matching(context_search_text(context))
            if not any(term in text for term in ("تصوير", "تسجيل")):
                continue
            if not any(term in text for term in ("محاضر", "محاضره", "محاضرة")):
                continue
            recording_contexts.append(context)
        if recording_contexts:
            return dedupe_preserve_order_contexts(recording_contexts[:2])
        return []

    normalized_question = normalize_for_matching(question)
    if "ضوابط" in normalized_question and any(term in normalized_question for term in ("جهه", "مسوول", "مختص")):
        authority_contexts = [
            context
            for context in rank_contexts_by_terms(
                contexts,
                include_any=("الجهة المسؤولة", "مسؤولية متابعة تنفيذ", "تتولى عمادة شؤون الطلاب"),
                prefer_article=("الماده الثامنه", "الجهه المسووله"),
            )
            if any(
                term in context_search_text(context)
                for term in ("الجهه المسووله", "مسووليه متابعه تنفيذ", "تتولي عماده شؤون الطلاب")
            )
        ][:2]
        if authority_contexts:
            return dedupe_preserve_order_contexts(authority_contexts)

    if (
        list_like_question_kind(question) == "rules"
        and "ضوابط" in normalized_question
        and any(term in normalized_question for term in ("الزي", "مظهر"))
        and not any(term in normalized_question for term in ("جهه", "مسوول", "مختص", "لجنه", "احال", "تحويل"))
    ):
        dress_rule_contexts = [
            context
            for context in rank_contexts_by_terms(
                contexts,
                include_any=("ارتداء", "ملابس", "اكسسوارات", "رسومات", "شعارات", "الشورت", "المظهر العام"),
                prefer_article=("الماده العاشره",),
            )
            if any(
                term in context_search_text(context)
                for term in ("ارتداء", "ملابس", "اكسسوارات", "رسومات", "شعارات", "الشورت")
            )
            and not any(
                term in context_search_text(context)
                for term in ("نموذج", "الحقول", "توقيع", "اقر", "الرقم الجامعي")
            )
        ][:3]
        if dress_rule_contexts:
            return dedupe_preserve_order_contexts(dress_rule_contexts)

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
                include_any=("الاسكان", "الاسكان الطلابي", "السكن الجامعي"),
                prefer_article=("شروط القبول", "شروط القبول بالاسكان الطلابي"),
            )[:4]
        ):
            mode_priority[context["id"]] = 1.0 - (index * 0.1)
    elif mode == "admission_conditions":
        for index, context in enumerate(
            rank_contexts_by_terms(
                contexts,
                include_any=("شروط الترشيح", "القبول", "الثانويه", "القدرات", "التحصيلي", "النسبه الموزونه"),
            )[:4]
        ):
            mode_priority[context["id"]] = 1.1 - (index * 0.1)

    scored: list[tuple[float, dict[str, Any], dict[str, float]]] = []
    for context in contexts:
        details = context_support_details(context, query_profile)
        scored.append((details["support_score"] + mode_priority.get(context["id"], 0.0), context, details))

    scored.sort(key=lambda item: item[0], reverse=True)
    gated_candidates = [
        item
        for item in scored
        if passes_relevance_gate(question, item[1], query_profile, item[2], language)
    ]
    if not gated_candidates:
        return []

    top_support_score = gated_candidates[0][0]
    support_window = 0.75 if language == "ar" and list_like_question_kind(question) == "system" else 0.45 if language == "ar" else 0.25
    preferred_source_type = explicit_source_type_preference(question) if language == "ar" else None
    primary_candidates = [
        item
        for item in gated_candidates
        if item[0] >= top_support_score - support_window
    ]
    primary_score, primary_context, primary_details = max(
        primary_candidates,
        key=lambda item: (
            int(preferred_source_type is not None and context_source_type(item[1]) == preferred_source_type),
            source_priority(context_source_type(item[1])) if language == "ar" else 0,
            item[0],
            float(item[1].get("score", 0.0)),
            float(item[1].get("lexical_score", 0.0)),
        ),
    )

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

    filtered = filtered or [primary_context]

    if language == "ar":
        secondary_context = select_secondary_clarification_context(
            question,
            contexts,
            primary_source_context(filtered),
            exclude_ids={context["id"] for context in filtered},
        )
        if secondary_context is not None:
            filtered.append(secondary_context)

    return dedupe_preserve_order_contexts(filtered)


def select_answer_contexts(question: str, contexts: list[dict[str, Any]], language: str) -> list[dict[str, Any]]:
    if not contexts:
        return []

    contexts = filter_weak_contexts(dedupe_preserve_order_contexts(contexts))

    if language != "ar":
        return contexts[:3]

    question_stems = build_question_stems(question, language)
    penalty_question = list_like_question_kind(question) == "penalties"
    rules_question = list_like_question_kind(question) == "rules"
    normalized_question = normalize_for_matching(question)

    def adjusted_answer_score(context: dict[str, Any]) -> float:
        score = context_answer_score(context, question_stems, language)
        content_text = normalize_for_matching(context.get("content", ""))

        if rules_question:
            item_count = len(extract_context_answer_items(context, question, max_items=3))
            if item_count > 0:
                score += 1.2 * item_count
            else:
                score -= 1.0

            if any(term in content_text for term in ("نموذج", "اقر انا", "توقيع", "الحقول", "الرقم الجامعي")):
                score -= 1.4
            if any(term in content_text for term in ("عمل جولات", "رصد كل مخالفه")):
                score -= 0.8
            if any(term in normalized_question for term in ("لجنه", "احال", "تحويل")):
                if any(term in content_text for term in ("تحال", "لجنه التحقيق", "تاديب الطلاب")):
                    score += 1.6
                if any(term in content_text for term in ("اتعهد", "المخالفه الثانيه")):
                    score -= 1.6

        if not penalty_question:
            return score

        metadata = context.get("metadata", {})
        metadata_text = normalize_for_matching(
            " ".join(
                part
                for part in (
                    metadata.get("article", ""),
                    metadata.get("section", ""),
                    metadata.get("title", ""),
                )
                if part
            )
        )

        if "العقوبات" in metadata_text:
            score += 1.4
        if "تنبيه شفهي" in content_text:
            score += 0.7
        if "تعهد كتابي" in content_text:
            score += 0.7
        if "رفع المخالفه" in content_text:
            score += 0.9

        if "نموذج" in content_text:
            score -= 1.0
        if "اقر انا" in content_text:
            score -= 1.1
        if "توقيع" in content_text:
            score -= 0.8
        if "الحقول" in content_text:
            score -= 0.8

        return score

    ranked = sorted(contexts, key=adjusted_answer_score, reverse=True)
    return ranked[:3]


def is_numeric_or_practical_question(question: str) -> bool:
    normalized_question = normalize_for_matching(question)
    return any(
        term in normalized_question
        for term in (
            "كم",
            "عدد",
            "رقم",
            "نسب",
            "حد",
            "معنى",
            "رمز",
            "نظام",
            "متطلبات",
            "شروط",
            "سياس",
        )
    )


def select_secondary_clarification_context(
    question: str,
    contexts: list[dict[str, Any]],
    primary_context: dict[str, Any] | None,
    *,
    exclude_ids: set[str] | None = None,
) -> dict[str, Any] | None:
    if primary_context is None:
        return None

    excluded = exclude_ids or set()
    primary_priority = source_priority(context_source_type(primary_context))
    if primary_priority <= 0:
        return None

    prefers_numeric = is_numeric_or_practical_question(question)
    normalized_question = normalize_for_matching(question)
    question_stems = build_question_stems(question, "ar")
    candidates: list[tuple[float, dict[str, Any]]] = []

    for context in contexts:
        if context["id"] in excluded:
            continue

        doc_priority = source_priority(context_source_type(context))
        if doc_priority >= primary_priority:
            continue

        snippet = extract_snippet(context, question, "ar")
        if not snippet:
            continue

        support_score = context_answer_score(context, question_stems, "ar")
        snippet_normalized = normalize_for_matching(snippet)
        if prefers_numeric and NUMBER_PATTERN.search(snippet):
            support_score += 0.8

        if any(code in normalized_question for code in ("dn", "ic", "wp", "wf", "np")) and any(
            code in snippet_normalized for code in ("dn", "ic", "wp", "wf", "np")
        ):
            support_score += 1.0

        if support_score < 0.95:
            continue

        candidates.append((support_score, context))

    if not candidates:
        return None

    candidates.sort(
        key=lambda item: (
            item[0],
            source_priority(context_source_type(item[1])),
            float(item[1].get("score", 0.0)),
            float(item[1].get("lexical_score", 0.0)),
        ),
        reverse=True,
    )
    return candidates[0][1]


def extract_context_answer_items(
    context: dict[str, Any],
    question: str,
    *,
    max_items: int = 3,
) -> list[str]:
    lines = clean_context_lines(context)
    if not lines:
        return []

    status_code_terms = extract_status_code_terms(question)
    if status_code_terms:
        matched_lines = []
        for line in lines:
            normalized_line = f" {normalize_for_matching(line)} "
            if any(f" {code} " in normalized_line for code in status_code_terms):
                matched_lines.append(build_answer_item_text(question, line))
        return dedupe_preserve_order([line for line in matched_lines if line])[:max_items]

    question_stems = build_question_stems(question, "ar")
    normalized_question = normalize_for_matching(question)
    committee_referral_question = any(term in normalized_question for term in ("لجنه", "احال", "تحويل"))
    dress_rules_question = (
        list_like_question_kind(question) == "rules"
        and "ضوابط" in normalized_question
        and any(term in normalized_question for term in ("الزي", "مظهر"))
    )

    scored_lines: list[tuple[float, int, str]] = []
    for index, line in enumerate(lines):
        score = score_line(line, question_stems)
        normalized_line = normalize_for_matching(line)
        if committee_referral_question:
            if any(term in normalized_line for term in ("تحال", "لجنه التحقيق", "تاديب الطلاب")):
                score += 2.0
            if any(term in normalized_line for term in ("اتعهد", "المخالفه الثانيه", "اقر انا", "نموذج")):
                score -= 2.0
        if dress_rules_question:
            if any(term in normalized_line for term in ("ارتداء", "ملابس", "اكسسوارات", "رسومات", "شعارات", "الشورت")):
                score += 1.4
            if any(term in normalized_line for term in ("الرقم الجامعي", "عمل جولات", "رصد كل مخالفه", "الحقول", "نموذج", "توقيع")):
                score -= 1.4
        scored_lines.append((score, index, line))

    scored_lines.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    if not scored_lines:
        return []

    best_score, best_index, _ = scored_lines[0]
    list_like = list_like_question_kind(question) is not None
    block_indices = anchored_block_indices(lines, best_index)
    items: list[str] = []

    if list_like and block_indices:
        for index in block_indices:
            line = lines[index]
            if is_heading_like_line(line) or not is_rule_like_line(line):
                continue
            cleaned_item = build_answer_item_text(question, line)
            if cleaned_item:
                items.append(cleaned_item)
        items = filter_items_for_question_kind(question, dedupe_preserve_order(items))
        if len(items) >= 2:
            return items[:max_items]

    fallback_items: list[str] = []
    for score, _, line in scored_lines:
        if score <= 0.0 and fallback_items:
            continue
        cleaned_item = build_answer_item_text(question, line)
        if not cleaned_item or is_heading_like_line(line):
            continue
        fallback_items.append(cleaned_item)
        if len(fallback_items) >= max_items:
            break

    fallback_items = filter_items_for_question_kind(question, dedupe_preserve_order(fallback_items))
    if fallback_items:
        return fallback_items[:max_items]

    if best_score <= 0.0:
        return []
    if list_like_question_kind(question) in {"penalties", "policy", "rules", "system"}:
        return []
    best_item = build_answer_item_text(question, lines[best_index])
    return [best_item] if best_item else []


def extract_snippet(context: dict[str, Any], question: str, language: str) -> str:
    lines = clean_context_lines(context)
    if not lines:
        return ""

    if language != "ar":
        return truncate_text(" ".join(lines[:3]), 320)

    extracted_items = extract_context_answer_items(context, question, max_items=3)
    if list_like_question_kind(question) is not None and len(extracted_items) >= 2:
        return "\n".join(f"- {item}" for item in extracted_items)
    if extracted_items:
        return " ".join(dedupe_preserve_order(extracted_items[:2]))

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


def normalize_reference_digits(text: str) -> str:
    return shared_normalize_reference_digits(text)


def parse_reference_order(article: str, title: str) -> tuple[int, int | float]:
    return shared_parse_reference_order(article, title)


def build_reference_entry(context: dict[str, Any], language: str, index: int) -> dict[str, Any] | None:
    return formatter.build_reference_entry(context, language, index, context=_formatter_context())


def sort_reference_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return formatter.sort_reference_entries(entries)


def build_reference(contexts: list[dict[str, Any]], language: str) -> str:
    return formatter.build_reference(contexts, language, context=_formatter_context())


def build_supporting_excerpt(context: dict[str, Any], question: str, language: str) -> str:
    formatter_context = _formatter_context()
    formatter_context.question = question
    return formatter.build_supporting_excerpt(context, question, language, context=formatter_context)


def has_substantive_supporting_excerpt(context: dict[str, Any], question: str, language: str) -> bool:
    excerpt = build_supporting_excerpt(context, question, language).strip()
    if not excerpt:
        return False
    return normalize_for_matching(excerpt) != normalize_for_matching(uncertainty_note(language))


def select_evidence_contexts(
    question: str,
    contexts: list[dict[str, Any]],
    language: str,
    *,
    max_items: int,
) -> list[dict[str, Any]]:
    selected = select_reference_contexts(question, contexts, max_items=max_items)
    if not selected:
        return []

    selected = filter_weak_contexts(selected)

    contexts_with_excerpt = [
        context for context in selected if build_supporting_excerpt(context, question, language).strip()
    ]
    if not contexts_with_excerpt:
        return selected

    substantive_contexts = [
        context for context in contexts_with_excerpt if has_substantive_supporting_excerpt(context, question, language)
    ]
    if substantive_contexts:
        complete_substantive = [context for context in substantive_contexts if not context_is_partial(context)]
        preferred = complete_substantive if complete_substantive else substantive_contexts
        return preferred[:max_items]

    complete_contexts = [context for context in contexts_with_excerpt if not context_is_partial(context)]
    preferred = complete_contexts if complete_contexts else contexts_with_excerpt
    return preferred[:max_items]


def select_reference_contexts(
    question: str,
    contexts: list[dict[str, Any]],
    *,
    max_items: int = 3,
) -> list[dict[str, Any]]:
    if not contexts:
        return []

    deduped_contexts = dedupe_preserve_order_contexts(contexts)
    status_code_contexts = select_status_code_contexts(question, deduped_contexts, max_items=max_items)
    if status_code_contexts:
        return status_code_contexts

    mode = detect_answer_mode(question, "ar")
    if mode == "missed_final":
        return rank_contexts_by_terms(
            deduped_contexts,
            include_any=("الطالب الغايب عن الاختبار النهايي", "غايب", "يغيب", "تغيبه", "صفر", "صفرا", "اختبار بديل"),
            prefer_article=("الماده الحاديه والثلاثون", "الماده الثانيه والثلاثون"),
        )[:max_items]
    if mode == "withdrawal":
        return rank_contexts_by_terms(
            deduped_contexts,
            include_any=("يجوز للطالب الانسحاب من مقرر دراسي", "ثلاثه انسحابات فقط", "طلب الانسحاب", "لا يسمح"),
            prefer_article=("الماده السابعه عشره", "البند 3", "البند 4", "البند 5", "البند 6", "البند 2"),
        )[:max_items]
    if mode == "lecture_recording":
        return rank_contexts_by_terms(
            deduped_contexts,
            require_all=("تصوير", "محاضر"),
            include_any=("تسجيل", "موافقه", "قواعد السلوك والانضباط الطلابي"),
            prefer_article=("الماده الخامسه",),
        )[:max_items]

    preferred_source_type = explicit_source_type_preference(question)
    list_like = list_like_question_kind(question) is not None
    list_kind = list_like_question_kind(question)
    status_codes = extract_status_code_terms(question)

    scoped_contexts = deduped_contexts
    if preferred_source_type:
        preferred_contexts = [
            context for context in deduped_contexts if context_source_type(context) == preferred_source_type
        ]
        if preferred_contexts:
            scoped_contexts = preferred_contexts
    elif list_like:
        primary_context = primary_source_context(deduped_contexts)
        primary_priority = source_priority(context_source_type(primary_context)) if primary_context else 0
        same_priority_contexts = [
            context
            for context in deduped_contexts
            if source_priority(context_source_type(context)) == primary_priority
        ]
        if same_priority_contexts:
            scoped_contexts = same_priority_contexts
    if status_codes:
        code_contexts = [
            context
            for context in scoped_contexts
            if any(f" {code} " in f" {context_search_text(context)} " for code in status_codes)
        ]
        if code_contexts:
            scoped_contexts = code_contexts

    question_stems = build_question_stems(question, "ar")
    entries: list[dict[str, Any]] = []
    for index, context in enumerate(scoped_contexts):
        entry = build_reference_entry(context, "ar", index)
        if not entry:
            continue
        excerpt = build_supporting_excerpt(context, question, "ar")
        if not excerpt:
            continue
        entry["context"] = context
        entry["support_score"] = context_answer_score(context, question_stems, "ar")
        entry["item_count"] = len(extract_context_answer_items(context, question, max_items=3)) if list_kind == "rules" else 0
        entry["preferred_source_match"] = int(
            preferred_source_type is not None and context_source_type(context) == preferred_source_type
        )
        entries.append(entry)

    if not entries:
        return scoped_contexts[:max_items]

    if list_like:
        if list_kind == "rules":
            item_rich_entries = [entry for entry in entries if entry["item_count"] > 0]
            if item_rich_entries:
                entries = item_rich_entries
            ordered_entries = sorted(
                entries,
                key=lambda item: (
                    -item["item_count"],
                    -item["support_score"],
                    item["order_key"][0],
                    item["order_key"][1],
                    item["index"],
                ),
            )
        else:
            ordered_entries = sort_reference_entries(entries)
    else:
        ordered_entries = sorted(
            entries,
            key=lambda item: (
                -item["preferred_source_match"],
                -item["source_priority"],
                -item["support_score"],
                item["order_key"][0],
                item["order_key"][1],
                item["index"],
            ),
        )

    return [entry["context"] for entry in ordered_entries[:max_items]]


def build_status_code_arabic_answer(question: str, contexts: list[dict[str, Any]]) -> str | None:
    codes = extract_status_code_terms(question)
    if not codes or not contexts:
        return None

    lines: list[str] = []
    selected_contexts = select_reference_contexts(question, contexts, max_items=3)
    for code_token in codes:
        code = code_token.upper()
        primary_meaning = ""
        guide_description = ""
        fallback_description = ""

        for context in selected_contexts:
            source_text = "\n".join(clean_context_lines(context)) or context.get("content", "")
            if not primary_meaning and context_source_type(context) == "regulation":
                primary_meaning = extract_status_code_meaning_from_text(source_text, code)
            if not guide_description and context_source_type(context) == "guide":
                guide_description = extract_status_code_description_from_text(source_text, code)
            if not fallback_description:
                fallback_description = extract_status_code_description_from_text(source_text, code)

        if not primary_meaning:
            for context in selected_contexts:
                source_text = "\n".join(clean_context_lines(context)) or context.get("content", "")
                primary_meaning = extract_status_code_meaning_from_text(source_text, code)
                if primary_meaning:
                    break

        description = guide_description or fallback_description
        if not primary_meaning and not description:
            continue

        if primary_meaning and not re.search(r"[\u0600-\u06FF]", primary_meaning):
            primary_meaning = STATUS_CODE_ARABIC_MEANINGS.get(code, primary_meaning)

        if primary_meaning and description:
            if normalize_for_matching(primary_meaning) in normalize_for_matching(description):
                line = f"{code}: {description}"
            else:
                line = f"{code}: في اللائحة يعني {primary_meaning}. وفي الدليل ورد أنه {description}"
        elif primary_meaning:
            line = f"{code}: {primary_meaning}"
        else:
            line = f"{code}: في الدليل ورد أنه {description}"

        lines.append(line.rstrip(" .،") + ".")

    if not lines:
        return None
    if len(lines) == 1:
        primary_context = primary_source_context(selected_contexts)
        intro = source_intro_phrase(context_source_type(primary_context or contexts[0]), "ar").rstrip(" ،")
        return f"{intro}: {lines[0]}"
    primary_context = primary_source_context(selected_contexts)
    header = source_intro_phrase(context_source_type(primary_context or contexts[0]), "ar").rstrip(" ،")
    return f"{header}:\n" + "\n".join(f"- {line}" for line in lines)


def is_withdrawal_question(question: str) -> bool:
    return question_router.is_withdrawal_question(question)


def is_missed_final_question(question: str) -> bool:
    return question_router.is_missed_final_question(question)


def is_attendance_limit_question(question: str) -> bool:
    return question_router.is_attendance_limit_question(question)


def extract_first_number(text: str) -> int | None:
    normalized_text = normalize_reference_digits(text)
    match = re.search(r"\d+", normalized_text)
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        return None


def build_attendance_limit_arabic_answer(question: str, contexts: list[dict[str, Any]]) -> str | None:
    if not is_attendance_limit_question(question) or not contexts:
        return None

    normalized_question = normalize_for_matching(question)
    asks_relationship_to_final = "اختبار" in normalized_question and any(
        term in normalized_question for term in ("علاقه", "علاقة", "له علاقه", "له علاقة")
    )
    ranked_contexts = rank_contexts_by_terms(
        contexts,
        include_any=("نسبه الحضور", "على الا تقل نسبه الحضور", "على ألا تقل نسبة الحضور", "حضور", "حرمان"),
        prefer_article=("الحرمان", "المادة الخامسة عشرة", "البند 1"),
    )

    final_exam_context = pick_context(
        contexts,
        include_any=("دخول الاختبار النهائي", "الحرمان", "رفع الحرمان"),
        article_terms=("الحرمان", "المادة الخامسة عشرة", "البند 1"),
    )

    for context in ranked_contexts[:3]:
        attendance_line = ""
        for line in clean_context_lines(context):
            normalized_line = normalize_for_matching(line)
            if "حضور" not in normalized_line or "نسب" not in normalized_line:
                continue
            if extract_first_number(line) is None:
                continue
            attendance_line = line.strip()
            break

        if not attendance_line:
            continue

        snippet = clean_supporting_source_snippet(attendance_line)

        focused_snippet = trim_from_phrase(
            snippet,
            (
                "على ألا تقل نسبة الحضور",
                "على الا تقل نسبة الحضور",
                "يحدد مجلس الجامعة نسبة الحد الأدنى",
            ),
        )
        if focused_snippet:
            snippet = focused_snippet

        if snippet.startswith(("على ألا تقل", "على الا تقل")):
            snippet = re.sub(r"^على\s+", "", snippet)
            snippet = f"يشترط {snippet}"

        number = extract_first_number(snippet)
        if number is None:
            continue

        relationship_note = ""
        if asks_relationship_to_final:
            if final_exam_context is not None:
                relationship_note = (
                    " ويرتبط ذلك بالاختبار النهائي لأن الحرمان يعني منع الطالب من دخول الاختبار النهائي إذا تدنت نسبة حضوره عن الحد الأدنى المطلوب."
                )
            else:
                relationship_note = " ويرتبط ذلك بالاختبار النهائي من جهة أن الحرمان يكون بحرمان الطالب من دخوله عند تدني نسبة الحضور."

        if "غياب" in normalized_question and "حضور" in normalize_for_matching(snippet) and 0 <= number <= 100:
            inferred_absence = 100 - number
            return (
                f"ورد في اللائحة أن {snippet.rstrip(' .،')}، "
                f"وبناءً على هذا النص فإن نسبة الغياب المقابلة تُستنتج حسابياً بأنها لا تتجاوز {inferred_absence}%، "
                f"ولا تظهر هنا نسبة غياب صريحة بلفظ مستقل.{relationship_note}"
            )

        return f"ورد في اللائحة أن {snippet.rstrip(' .،')}.{relationship_note}"

    return "لم أجد في النص المتاح نسبة غياب صريحة، وإنما ظهر فقط اشتراط حد أدنى للحضور عندما يكون ذلك مذكوراً بوضوح."


def _dedupe_subsumption(items: list[str]) -> list[str]:
    """Remove items that are a prefix of a longer item (keep the longer one)."""
    normalized_items = [(normalize_for_matching(item), item) for item in items]
    result: list[str] = []
    for i, (norm_i, orig_i) in enumerate(normalized_items):
        subsumed = False
        for j, (norm_j, _) in enumerate(normalized_items):
            if i != j and norm_j.startswith(norm_i) and len(norm_j) > len(norm_i):
                subsumed = True
                break
        if not subsumed:
            result.append(orig_i)
    return result


def build_list_like_arabic_answer(question: str, contexts: list[dict[str, Any]]) -> str | None:
    if list_like_question_kind(question) is None or not contexts:
        return None

    max_items = 5 if list_like_question_kind(question) in {"policy", "system", "penalties"} else 4
    items: list[str] = []
    for context in select_reference_contexts(question, contexts, max_items=4):
        items.extend(extract_context_answer_items(context, question, max_items=max_items))
        items = dedupe_preserve_order(items)
        if len(items) >= max_items:
            break

    if not items:
        return None

    items = _dedupe_subsumption(items)[:max_items]
    intro = list_like_intro(question, item_count=len(items), contexts=contexts)
    if len(items) == 1:
        return f"{intro}: {items[0]}"
    return f"{intro}:\n" + "\n".join(f"- {item}" for item in items[:max_items])


def detect_answer_mode(question: str, language: str) -> str:
    return question_router.detect_answer_mode(question, language)


def route_question(
    question: str,
    language: str,
    *,
    fallback_service: FallbackService,
) -> dict[str, Any]:
    return question_router.route_question(
        question,
        context={"fallback_service": fallback_service},
        language=language,
    )


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

        score += 0.2 * source_priority(context_source_type(context))

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
    label = build_display_title(
        document_title=metadata.get("document_title", ""),
        article=metadata.get("article", ""),
        section=metadata.get("section", ""),
        fallback_title=metadata.get("title", ""),
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
        lines.append(f"- {source_reference_tag(context_source_type(context), 'ar')} {label}: {cleaned_snippet}")

    return "\n".join(lines)


def apply_source_aware_arabic_wording(
    question: str,
    answer: str,
    contexts: list[dict[str, Any]],
) -> str:
    cleaned = (answer or "").strip()
    if not cleaned or cleaned == FALLBACK_AR or not contexts:
        return cleaned

    if is_comparison_question(question):
        return cleaned

    primary_context = primary_source_context(contexts)
    if primary_context is None:
        return cleaned

    primary_intro = source_intro_phrase(context_source_type(primary_context), "ar")
    first_line = cleaned.split("\n", 1)[0]
    if cleaned.startswith(
        (
            "وفق اللائحة",
            "وفق السياسة",
            "وفق الدليل",
            "وفق الأسئلة الشائعة",
            "ورد في اللائحة",
            "ورد في السياسة",
            "ورد في الدليل",
            "ورد في الأسئلة الشائعة",
            "بحسب ",
            "وفي الدليل ورد",
            "وفي الأسئلة الشائعة ورد",
            "كما ورد في اللائحة",
            "كما ورد في السياسة",
        )
    ) or any(phrase in first_line for phrase in ("في اللائحة", "وفق اللائحة", "في السياسة", "وفق السياسة")):
        return cleaned

    if cleaned.startswith(("لم أجد في اللائحة", "لم أجد في النص المتاح رقم", "لم أجد في النص المتاح عدد")) and (
        "اللائحة" in cleaned or "السياسة" in cleaned or "الدليل" in cleaned or "الأسئلة الشائعة" in cleaned
    ):
        return cleaned

    if is_yes_no_question(question, "ar"):
        if cleaned.startswith("نعم،"):
            remainder = cleaned[len("نعم،") :].strip()
            return f"نعم، {primary_intro}{remainder}".strip()
        if cleaned.startswith("لا،"):
            remainder = cleaned[len("لا،") :].strip()
            return f"لا، {primary_intro}{remainder}".strip()

    return f"{primary_intro}{cleaned}".strip()


def format_yes_no_arabic_answer(question: str, answer: str, contexts: list[dict[str, Any]]) -> str:
    cleaned = (answer or "").strip()
    if not cleaned or cleaned == FALLBACK_AR:
        return cleaned

    normalized_question = normalize_for_matching(question)
    normalized_answer = normalize_for_matching(cleaned)
    primary_context = primary_source_context(contexts)
    primary_is_regulation = context_source_type(primary_context) == "regulation" if primary_context else False

    def regulation_source_statement(body: str) -> str:
        statement = strip_leading_connector(limit_answer_sentences(dedupe_answer_text(body), max_sentences=2)).rstrip(" .،")
        if not statement:
            return cleaned
        article = (primary_context or {}).get("metadata", {}).get("article", "") if primary_context else ""
        if article:
            return f"بحسب {article}، {statement}."
        return f"ورد في اللائحة أن {statement}."

    if "انسحاب" in normalized_question and asks_lower_limit(normalized_question):
        return "بحسب النص، لا يسمح بالانسحاب إذا أصبح العبء أقل من الحد الأدنى بعد تنفيذ الانسحاب."

    if cleaned.startswith("نعم،") or cleaned.startswith("لا،"):
        if primary_is_regulation:
            remainder = cleaned.split("،", 1)[1].strip() if "،" in cleaned else cleaned[3:].strip()
            return regulation_source_statement(remainder)
        return limit_answer_sentences(cleaned, max_sentences=2)

    if "مجلس الجامعه" in normalized_question and any(
        "مجلس الجامعه" in context_search_text(context) and "محدد" in context_search_text(context)
        for context in contexts
    ):
        return "ورد في النص أن العبء الدراسي محدد من مجلس الجامعة."

    if cleaned.startswith("لم أجد في النص المتاح رقم") or cleaned.startswith("لم أجد في النص المتاح عدد"):
        return f"ورد في النص الآتي: {cleaned}"

    if any(token in normalized_answer for token in ("لا يسمح", "لا يجوز", "ممنوع", "محظور")):
        body = strip_leading_connector(limit_answer_sentences(cleaned, max_sentences=1))
        if primary_is_regulation:
            return regulation_source_statement(body)
        if body.startswith("لا"):
            return f"لا، {body}"
        return f"لا، {body.rstrip(' .')}."

    if cleaned.startswith("نعم") or cleaned.startswith("لا"):
        if primary_is_regulation:
            body = cleaned.split("،", 1)[1].strip() if "،" in cleaned else cleaned[3:].strip()
            return regulation_source_statement(body)
        return limit_answer_sentences(cleaned, max_sentences=2)

    if any(token in normalized_answer for token in ("يجوز", "يسمح", "يحق", "محدد من مجلس الجامعه")):
        body = strip_leading_connector(limit_answer_sentences(cleaned, max_sentences=1))
        if primary_is_regulation:
            return regulation_source_statement(body)
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
    cleaned = re.sub(r"^(?:ج|الجواب)\s*[:：]\s*", "", cleaned)
    cleaned = cleaned.replace("ويذكر النص المسترجع من هذه العقوبات:", "ومن العقوبات المذكورة في اللائحة:")
    cleaned = re.sub(r"في النص(?:وص)? المسترجع(?:ة|ه)?", "في اللائحة", cleaned)
    cleaned = re.sub(r"النص(?:وص)? المسترجع(?:ة|ه)?", "اللائحة", cleaned)
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


def polish_multiline_arabic_answer_text(text: str) -> str:
    lines: list[str] = []
    for raw_line in (text or "").splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.startswith("-"):
            bullet_body = polish_arabic_answer_text(stripped[1:].strip())
            if bullet_body:
                lines.append(f"- {bullet_body}")
            continue
        line = polish_arabic_answer_text(stripped)
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def format_inline_arabic_bullets(answer: str) -> str:
    cleaned = (answer or "").strip()
    if not cleaned or "\n-" in cleaned:
        return cleaned
    if "•" not in cleaned and "▪" not in cleaned:
        return cleaned

    bulletized = re.sub(r"\s*[•▪]\s*", "\n- ", cleaned)
    bulletized = re.sub(r"\s+(مرتبة الشرف الثانية:)", r"\n\1", bulletized)
    bulletized = re.sub(r"\n{3,}", "\n\n", bulletized).strip()
    return bulletized


def maybe_format_arabic_list_answer(answer: str) -> str:
    cleaned = (answer or "").strip()
    if not cleaned or "\n-" in cleaned:
        return cleaned

    cleaned = format_inline_arabic_bullets(cleaned)
    if "\n-" in cleaned:
        return cleaned

    intro, separator, tail = cleaned.partition(":")
    if not separator or not tail.strip():
        return cleaned

    normalized_intro = normalize_for_matching(intro)
    if not any(
        phrase in normalized_intro
        for phrase in (
            "من الشروط",
            "الشروط الاضافيه",
            "من العقوبات",
            "الخطوات",
            "القواعد",
        )
    ):
        return cleaned

    raw_items = [item.strip() for item in re.split(r"[؛;]", tail) if item.strip()]
    if len(raw_items) < 2:
        return cleaned

    starter_pattern = re.compile(
        r"^(?:و)?(?:ألا|الا|أن|ان|عدم|استكمال|اجتياز|الحصول|الالتزام|التقيد|تقديم|الرسوب|الحرمان)\b"
    )
    starter_count = sum(1 for item in raw_items if starter_pattern.match(item))
    if starter_count < 2:
        return cleaned

    bullet_lines = [f"- {item.rstrip(' .،؛')}" for item in raw_items]
    return f"{intro.strip()}:\n" + "\n".join(bullet_lines)


def polish_english_answer_text(text: str) -> str:
    cleaned = CLAUSE_NUMBER_PATTERN.sub("", (text or "").strip())
    cleaned = cleaned.replace("Yes, The student submits", "Yes. The student submits")
    cleaned = cleaned.replace("Yes, the student submits", "Yes. The student submits")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return dedupe_answer_text(cleaned)


def normalize_english_status_code_meanings(text: str) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        return ""

    sentences = split_sentences(cleaned)
    normalized_sentences: list[str] = []

    for sentence in sentences:
        updated_sentence = sentence.strip()
        upper_sentence = updated_sentence.upper()
        for code, meaning in STATUS_CODE_ENGLISH_MEANINGS.items():
            if code not in upper_sentence:
                continue
            if "=" in updated_sentence:
                updated_sentence = f"{meaning} ({code})"
                break
        normalized_sentences.append(updated_sentence.rstrip(" ."))

    return ". ".join(sentence for sentence in normalized_sentences if sentence).strip()


def build_mode_based_arabic_answer(
    question: str,
    contexts: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], bool] | None:
    mode = detect_answer_mode(question, "ar")
    if mode == "general":
        return None
    if mode in {"attendance_penalty", "smoking"}:
        return None

    used_contexts: list[dict[str, Any]] = []
    parts: list[str] = []

    if mode == "housing_conditions":
        # Only pull from housing admission/eligibility contexts (exclude denial/punishment and operational rules).
        ranked = rank_contexts_by_terms(
            contexts,
            include_any=("الاسكان", "الاسكان الطلابي", "السكن الجامعي"),
            prefer_article=("شروط القبول", "شروط القبول بالاسكان الطلابي"),
        )
        example_contexts = [
            context
            for context in ranked
            if "شروط القبول" in context_search_text(context)
            and "ضوابط الدخول والخروج" not in context_search_text(context)
        ][:6]
        deny_terms = ("حرمان", "الحرمان", "عقوب", "مخالف", "طرد", "اخلاء", "نهائي", "منع", "ممنوع")
        condition_lines: list[str] = []
        for context in example_contexts:
            for line in clean_context_lines(context):
                normalized_line = normalize_for_matching(line)
                if "[غير واضح في المصدر]" in line or normalized_line.endswith(":"):
                    continue
                if any(term in normalized_line for term in deny_terms):
                    continue
                if not any(term in normalized_line for term in ("يشترط", "الا يكون", "ألا يكون", "ان يكون", "- ")):
                    continue
                condition_lines.append(normalize_answer_item(line))
        condition_lines = dedupe_preserve_order(condition_lines)
        if not condition_lines:
            return None
        used_contexts.extend(example_contexts)
        parts.append("شروط القبول في الإسكان الطلابي حسب اللائحة:")
        parts.append("- " + "\n- ".join(condition_lines[:8]).rstrip(" .،"))
        unclear = contexts_have_quality_risk(example_contexts)
        return " ".join(parts).strip(), dedupe_preserve_order_contexts(used_contexts), unclear

    if mode == "load_limit":
        normalized_question = normalize_for_matching(question)
        asks_upper = asks_upper_limit(normalized_question)
        asks_lower = asks_lower_limit(normalized_question)
        asks_range = asks_upper and asks_lower
        asks_number = any(term in normalized_question for term in ("كم", "عدد", "رقم محدد", "يوجد رقم", "المسموح"))

        if asks_range:
            definition_context = pick_context(
                contexts,
                article_terms=("الحد الادني للعبء الدراسي",),
                include_any=("الحد الادني للعبء الدراسي", "العبء الدراسي"),
            )
            practical_context = pick_context(
                contexts,
                article_terms=("الحد الاعلي للعبء الدراسي",),
                include_any=("الحد الاعلي للعبء الدراسي", "العبء الدراسي"),
            )
        elif asks_upper:
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
        main_contexts = [context for context in (definition_context, practical_context) if context is not None]
        primary_context = primary_source_context(main_contexts)
        clarification_context = next(
            (
                context
                for context in rank_contexts_by_terms(
                    contexts,
                    include_any=(
                        "الحد الاعلي",
                        "الحد الادني",
                        "الوحدات",
                        "الفصل الصيفي",
                        "العبء الدراسي",
                    ),
                    exclude_ids={context["id"] for context in main_contexts},
                )
                if source_priority(context_source_type(context))
                < source_priority(context_source_type(primary_context or context))
                and extract_limit_number_text(extract_snippet(context, question, "ar"))
            ),
            None,
        )
        clarification_text = (
            extract_limit_number_text(extract_snippet(clarification_context, question, "ar"))
            if clarification_context
            else ""
        )
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
            if clarification_text and clarification_text != explicit_number and clarification_context is not None:
                used_contexts.append(clarification_context)
                parts.append(
                    f"{source_intro_phrase(context_source_type(clarification_context), 'ar', secondary=True)}"
                    f"{clarification_text.rstrip(' .،')}."
                )
        elif definition_text or practical_text:
            if asks_range:
                prefix = "لم أجد في اللائحة رقمًا محددًا للحدين الأدنى والأعلى للساعات، لكن اللائحة تعرف الحدين ضمن ضوابط العبء الدراسي"
            elif asks_upper:
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
                if asks_range:
                    detail_parts.append(practical_text.rstrip(" .،"))
                elif "محدده من مجلس الجامعه" in normalized_practical:
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
                if clarification_text and clarification_context is not None:
                    used_contexts.append(clarification_context)
                    parts.append(
                        f"{source_intro_phrase(context_source_type(clarification_context), 'ar', secondary=True)}"
                        f"{clarification_text.rstrip(' .،')}."
                    )

    elif mode == "gpa_formula":
        semester_context = pick_context(
            contexts,
            article_terms=("المعدل الفصلي",),
            include_any=("حاصل قسمة", "مجموع النقاط", "الوحدات"),
        )
        cumulative_context = pick_context(
            contexts,
            article_terms=("المعدل التراكمي",),
            include_any=("حاصل قسمة", "مجموع النقاط", "الوحدات"),
        )
        guide_context = pick_context(
            contexts,
            include_any=("طريقة حساب المعدل",),
        )

        if semester_context is not None:
            used_contexts.append(semester_context)
            parts.append(
                "يُحسب المعدل الفصلي بقسمة مجموع النقاط على مجموع الوحدات المقررة، "
                "وتُحسب النقاط بضرب الوحدة المقررة في وزن التقدير."
            )
        if cumulative_context is not None:
            used_contexts.append(cumulative_context)
            parts.append(
                "ويُحسب المعدل التراكمي بقسمة مجموع النقاط التي حصل عليها الطالب في جميع المقررات "
                "على مجموع الوحدات المقررة لها."
            )
        if guide_context is not None:
            guide_text = extract_matching_lines(
                guide_context,
                include_any=("طريقة حساب المعدل",),
                limit=1,
            )
            if guide_text:
                used_contexts.append(guide_context)
                parts.append(f"{source_intro_phrase(context_source_type(guide_context), 'ar', secondary=True)}{guide_text.rstrip(' .،')}.")

    elif mode == "attendance_penalty":
        penalty_context = pick_context(
            contexts,
            article_terms=("الحرمان",),
            include_any=("دخول الاختبار النهائي", "الحضور", "الحرمان"),
        )
        rule_context = pick_context(
            contexts,
            article_terms=("المادة الخامسة عشرة", "البند 1"),
            include_any=("رفع الحرمان", "الحضور", "الاختبار النهائي", "عذر"),
        )
        excuse_context = pick_context(
            contexts,
            article_terms=("البند 3",),
            include_any=("غائب بعذر", "الحرمان"),
        )

        penalty_text = (
            extract_matching_lines(
                penalty_context,
                include_any=("دخول الاختبار النهائي", "الحضور", "الحرمان"),
                limit=1,
            )
            if penalty_context
            else ""
        )
        rule_text = (
            extract_matching_lines(
                rule_context,
                include_any=("رفع الحرمان", "الحضور", "الاختبار النهائي", "عذر"),
                limit=1,
            )
            if rule_context
            else ""
        )
        excuse_text = (
            extract_matching_lines(
                excuse_context,
                include_any=("غائب بعذر", "الحرمان"),
                limit=1,
            )
            if excuse_context
            else ""
        )

        if penalty_text:
            used_contexts.append(penalty_context)
            parts.append(
                "ورد أن الحرمان يكون بحرمان الطالب من دخول الاختبار النهائي "
                "بسبب تدني نسبة حضوره عن الحد الأدنى المطلوب."
            )
        elif rule_text or excuse_text:
            parts.append(
                "وردت أحكام تتعلق بالحرمان من الاختبار النهائي عند تدني نسبة الحضور، "
                "ولم يظهر فيها تعداد مستقل ومفصل لعقوبات الغياب."
            )

        if rule_text and rule_context is not None:
            used_contexts.append(rule_context)
            parts.append(
                "كما ورد أنه يجوز رفع الحرمان والسماح بدخول الاختبار النهائي إذا قُبل العذر، "
                "على ألا تقل نسبة الحضور عن 60%."
            )
        if excuse_text and excuse_context is not None:
            used_contexts.append(excuse_context)
            parts.append("ويرصد الغياب بعذر ولا يُحسب من نسبة الحرمان.")

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
        withdrawal_pool = dedupe_preserve_order_contexts(
            contexts + fallback_service.get_fallback_context("withdrawal", limit=4)
        )
        general_ranked = rank_contexts_by_terms(
            withdrawal_pool,
            include_any=("يجوز", "طلب الانسحاب", "الانسحاب من المقرر"),
            prefer_article=("الماده السابعه عشره", "المادة السابعة عشرة"),
        )
        general_context = general_ranked[0] if general_ranked else None
        limit_context = pick_context(
            withdrawal_pool,
            article_terms=("البند 3",),
            include_any=("ثلاثه انسحابات فقط",),
        )
        restrictions = rank_contexts_by_terms(
            withdrawal_pool,
            require_all=("لا يسمح", "انسحاب"),
            prefer_article=("البند 4", "البند 5", "البند 6", "البند 2"),
        )

        general_text = (
            extract_matching_lines(
                general_context,
                include_any=("يجوز", "طلب الانسحاب", "الانسحاب من المقرر"),
                limit=1,
            )
            if general_context
            else ""
        )
        limit_text = (
            extract_matching_lines(
                limit_context,
                include_any=("ثلاثه انسحابات فقط",),
                limit=1,
            )
            if limit_context
            else ""
        )
        restriction_texts: list[str] = []
        for context in restrictions[:4]:
            text = extract_matching_lines(context, require_all=("لا يسمح", "انسحاب"), limit=1)
            if text:
                restriction_texts.append(text)

        if general_text or general_context is not None:
            used_contexts.append(general_context)
            parts.append("نعم، يجوز الانسحاب من المقرر وفق المادة السابعة عشرة والقواعد التنفيذية.")
        if limit_text and limit_context is not None:
            used_contexts.append(limit_context)
            parts.append(
                "ومن أهم الضوابط أن الطالب يسمح له بثلاثة انسحابات فقط من المقررات خلال كامل مدة الدراسة بنفس الرقم الجامعي، "
                "ويجوز لمجلس الكلية أو من يفوضه الاستثناء من ذلك."
            )
        if restriction_texts:
            used_contexts.extend(restrictions[:4])
            restriction_summary = []
            normalized_restrictions = [normalize_for_matching(text) for text in restriction_texts]
            if any("المستويات الدراسيه الاقل" in text or "المستوى الدراسي الحالي" in text for text in normalized_restrictions):
                restriction_summary.append("لا يسمح بالانسحاب من المقررات التي في مستويات أدنى من المستوى الدراسي الحالي إلا باستثناء")
            if any("اقل من الحد الادني" in text or "الحد الادني للعبء الدراسي" in text for text in normalized_restrictions):
                restriction_summary.append("ولا إذا أصبح العبء أقل من الحد الأدنى بعد تنفيذ الانسحاب")
            if any("حرمان" in text for text in normalized_restrictions):
                restriction_summary.append("ولا بعد الحرمان من المقرر")
            if any("الفصل الصيفي" in text for text in normalized_restrictions):
                restriction_summary.append("ولا في الفصل الصيفي")
            if restriction_summary:
                parts.append("لكن من القيود المهمة: " + "، ".join(dedupe_preserve_order(restriction_summary)) + ".")
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
        penalty_pool = [
            context
            for context in dedupe_preserve_order_contexts(contexts + fallback_service.get_fallback_context("penalty", limit=4))
            if "الماده الثامنه" in context_search_text(context)
            and "الإجراءات المتبعة في حالة الغش" not in context_search_text(context)
        ]
        ranked_penalty_contexts = rank_contexts_by_terms(
            penalty_pool or contexts,
            include_any=("الاختبار الدوري", "الاختبار النصفي", "الاختبار النهائي", "المقرر", "فصل", "حرمان", "راسب"),
            prefer_article=("الماده الثامنه",),
        )
        example_contexts = ranked_penalty_contexts[:3]

        penalty_lines: list[str] = []
        for context in example_contexts:
            for line in clean_context_lines(context):
                normalized_line = normalize_for_matching(line)
                if "[غير واضح في المصدر]" in line or normalized_line.endswith(":"):
                    continue
                if not any(
                    term in normalized_line
                    for term in (
                        "الاختبار الدوري",
                        "الاختبار النصفي",
                        "الاختبار النهائي",
                        "راسب",
                        "المقرر",
                        "الفصل من الجامعه",
                        "الفصل النهايي من الجامعه",
                    )
                ):
                    continue
                penalty_lines.append(normalize_answer_item(line))

        penalty_lines = dedupe_preserve_order(penalty_lines)

        if penalty_lines:
            used_contexts.extend(example_contexts)
            parts.append("الغش أو محاولة الغش يعاقب بإحدى العقوبات الواردة من البند 7 إلى البند 15 من المادة الثامنة.")

            summary_parts: list[str] = []
            normalized_items = [normalize_for_matching(item) for item in penalty_lines]
            if any("الاختبار الدوري" in item or "الاختبار النصفي" in item for item in normalized_items):
                summary_parts.append("ومنها الحرمان من درجة الاختبار الدوري أو النصفي")
            if any("راسب" in item and "المقرر" in item for item in normalized_items):
                summary_parts.append("والرسوب في المقرر")
            if any("الاختبار النهائي" in item for item in normalized_items):
                summary_parts.append("والحرمان من درجة الاختبار النهائي")
            if any("الفصل النهايي" in item or "الفصل النهائي" in item for item in normalized_items):
                summary_parts.append("وقد تصل العقوبة إلى الفصل النهائي من الجامعة")

            if summary_parts:
                parts.append(" ".join(summary_parts) + ".")
            else:
                parts.append("ومن العقوبات المذكورة: " + "، ".join(penalty_lines[:4]).rstrip(" .،") + ".")

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

    unclear = contexts_have_quality_risk(used_contexts)
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
    negative_snippets = [snippet for snippet in snippets if any(token in snippet for token in NEGATIVE_AR)]
    negative_norms = {normalize_for_matching(snippet) for snippet in negative_snippets}
    positive = next(
        (
            snippet
            for snippet in snippets
            if any(token in snippet for token in POSITIVE_AR)
            and normalize_for_matching(snippet) not in negative_norms
        ),
        "",
    )

    if yes_no and positive and negative_snippets:
        negative_text = " ".join(dedupe_preserve_order(negative_snippets[:2]))
        answer = f"نعم، {positive}"
        if negative_text:
            answer += f" لكن {negative_text}"
    elif yes_no and negative_snippets:
        answer = f"لا، {negative_snippets[0]}"
    elif yes_no and positive:
        answer = f"نعم، {positive}"
    elif list_like_question_kind(question) == "penalties":
        answer = snippets[0]
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
    return formatter.build_english_answer(arabic_answer, reference, context=_formatter_context())


def compose_arabic_response(
    question: str,
    contexts: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], bool]:
    mode_based = build_mode_based_arabic_answer(question, contexts)
    if mode_based:
        return mode_based

    primary_context = primary_source_context(contexts)
    primary_priority = source_priority(context_source_type(primary_context)) if primary_context else 0
    primary_contexts = [
        context for context in contexts if source_priority(context_source_type(context)) == primary_priority
    ]
    selection_pool = primary_contexts or contexts
    selected_contexts = select_answer_contexts(question, selection_pool, "ar")
    secondary_context = select_secondary_clarification_context(
        question,
        contexts,
        primary_source_context(selected_contexts or selection_pool),
        exclude_ids={context["id"] for context in selected_contexts},
    )
    snippets = [extract_snippet(context, question, "ar") for context in selected_contexts]
    snippets = dedupe_preserve_order([snippet for snippet in snippets if snippet])

    if not snippets:
        return FALLBACK_AR, [], False

    unclear = contexts_have_quality_risk(selected_contexts) or any(
        "[غير واضح في المصدر]" in snippet for snippet in snippets
    ) or all(context_is_partial(context) for context in selected_contexts)
    direct_answer = build_direct_arabic_answer(question, snippets, unclear)
    used_contexts = selected_contexts[:]
    if secondary_context is not None:
        used_contexts.append(secondary_context)
    return direct_answer, dedupe_preserve_order_contexts(used_contexts), unclear


def build_arabic_answer(question: str, contexts: list[dict[str, Any]]) -> str:
    formatter_context = _formatter_context()
    formatter_context.question = question
    return formatter.build_arabic_answer(question, contexts, context=formatter_context)


def filter_contexts_for_generation(
    question: str,
    contexts: list[dict[str, Any]],
    language: str,
    *,
    route: RouteDecision,
    fallback_service: FallbackService,
) -> list[dict[str, Any]]:
    """
    Wrapper for augment_contexts_for_route for use in ChatService and other orchestration logic.
    """
    return augment_contexts_for_route(
        question,
        contexts,
        language,
        route=route,
        fallback_service=fallback_service,
    )

class ChatService:
    def __init__(
        self,
        *,
        router: QuestionRouter,
        fallback_service: FallbackService,
        formatter: AnswerFormatterService,
        search_fn: Any = search,
        detect_language_fn: Any = detect_language,
        rewrite_query_fn: Any = rewrite_query,
        filter_contexts_fn: Any = filter_contexts_for_generation,
        compose_arabic_response_fn: Any = compose_arabic_response,
        select_evidence_contexts_fn: Any = select_evidence_contexts,
    ) -> None:
        self.router = router
        self.fallback_service = fallback_service
        self.formatter = formatter
        self.search_fn = search_fn
        self.detect_language_fn = detect_language_fn
        self.rewrite_query_fn = rewrite_query_fn
        self.filter_contexts_fn = filter_contexts_fn
        self.compose_arabic_response_fn = compose_arabic_response_fn
        self.select_evidence_contexts_fn = select_evidence_contexts_fn

    def route_question(self, question: str, language: str, *, top_k: int) -> RouteDecision:
        route_data = self.router.route_question(
            question,
            context={"fallback_service": self.fallback_service},
            language=language,
        )
        mode = str(route_data["mode"])
        retrieval_top_k = (
            max(top_k, 12)
            if mode in {"load_limit", "penalty", "attendance_penalty", "gpa_formula", "housing_conditions"}
            else max(top_k, 8)
        )
        return RouteDecision.from_mapping(
            route_data,
            retrieval_top_k=retrieval_top_k,
            is_attendance_limit=self.router.is_attendance_limit_question(question) if language == "ar" else False,
        )

    def answer_question(self, question: str, top_k: int = 4) -> dict[str, Any]:
        original_question = question
        language = self.detect_language_fn(original_question)
        working_question = self.rewrite_query_fn(original_question) if language == "ar" else original_question

        if is_status_code_query(original_question) or is_status_code_query(working_question):
            language = "ar"
        route = self.route_question(working_question, language, top_k=top_k)
        normalized_query = (
            build_query_profile(working_question)["normalized_query"]
            if language == "ar"
            else normalize_for_matching(working_question)
        )
        contexts = self.search_fn(working_question, top_k=route.retrieval_top_k)
        emit_chat_diagnostics(
            stage="retrieval",
            original_question=original_question,
            working_question=working_question,
            normalized_query=normalized_query,
            language=language,
            route=route,
            retrieved_contexts=contexts,
        )
        filtered_contexts = self.filter_contexts_fn(
            working_question,
            contexts,
            language,
            route=route,
            fallback_service=self.fallback_service,
        )

        coverage_assessment = assess_category_source_coverage(
            working_question,
            filtered_contexts if filtered_contexts else contexts,
        )

        if not filtered_contexts:
            if coverage_assessment is not None and coverage_assessment["has_gap"]:
                answer = build_coverage_gap_fallback(language, coverage_assessment["category"])
                fallback_reason = f"coverage_gap_{coverage_assessment['category']}"
            else:
                answer = FALLBACK_AR if language == "ar" else FALLBACK_EN
                fallback_reason = "no_retrieval_results" if not contexts else "no_mode_aligned_contexts" if mode_requires_strict_context_match(route.mode) else "no_contexts_after_filtering"
            emit_chat_diagnostics(
                stage="fallback",
                original_question=original_question,
                working_question=working_question,
                normalized_query=normalized_query,
                language=language,
                route=route,
                retrieved_contexts=contexts,
                filtered_contexts=[],
                fallback_reason=fallback_reason,
                answer=answer,
            )
            return self.formatter.build_response(
                original_question,
                language,
                answer,
                [],
                route_mode=route.mode,
                confidence="low",
                coverage=coverage_assessment if coverage_assessment is not None else None,
            )

        if coverage_assessment is not None and coverage_assessment["has_gap"]:
            answer = build_coverage_gap_fallback(language, coverage_assessment["category"])
            emit_chat_diagnostics(
                stage="fallback",
                original_question=original_question,
                working_question=working_question,
                normalized_query=normalized_query,
                language=language,
                route=route,
                retrieved_contexts=contexts,
                filtered_contexts=filtered_contexts,
                fallback_reason=f"coverage_gap_{coverage_assessment['category']}",
                answer=answer,
            )
            return self.formatter.build_response(
                original_question,
                language,
                answer,
                [],
                route_mode=route.mode,
                confidence="low",
                coverage=coverage_assessment,
            )

        direct_arabic_answer, used_contexts, unclear = self.compose_arabic_response_fn(working_question, filtered_contexts)
        answer_state = AnswerComputation(
            direct_answer=direct_arabic_answer,
            used_contexts=used_contexts,
            unclear=unclear,
        )
        formatter_context = _formatter_context()
        formatter_context.question = working_question
        formatter_context.used_contexts = used_contexts
        formatter_context.unclear = unclear
        formatter_context.route = route
        formatter_context.answer_state = answer_state
        contexts_for_answer = filtered_contexts
        if language == "ar" and contexts_for_answer:
            normalized_question = normalize_for_matching(working_question)
            is_cheating_penalty_question = (
                list_like_question_kind(working_question) == "penalties"
                and penalty_question_domain(working_question) == "cheating"
            )
            if is_cheating_penalty_question:
                housing_terms = ("سكن", "اسكان", "الاسكان", "الاقامه بالسكن", "الاقامة بالسكن")
                non_exam_terms = ("العمل", "البحث", "التقرير", "الواجب")
                is_exam_scoped = "اختبار" in normalized_question
                filtered: list[dict[str, Any]] = []
                for context in contexts_for_answer:
                    content = context.get("content", "")
                    if not isinstance(content, str) or not content.strip():
                        filtered.append(context)
                        continue

                    keep_lines: list[str] = []
                    for line in content.splitlines():
                        normalized_line = normalize_for_matching(line)
                        if any(term in normalized_line for term in housing_terms):
                            continue
                        if is_exam_scoped and any(term in normalized_line for term in non_exam_terms):
                            continue
                        keep_lines.append(line)

                    sanitized_content = "\n".join(keep_lines).strip()
                    if not sanitized_content:
                        continue

                    # Keep metadata/scores but remove excluded lines from content.
                    sanitized_context = dict(context)
                    sanitized_context["content"] = sanitized_content
                    filtered.append(sanitized_context)

                contexts_for_answer = filtered

        answer = (
            self.formatter.build_arabic_answer(working_question, contexts_for_answer, context=formatter_context)
            if language == "ar"
            else self.formatter.format_answer(
                direct_arabic_answer,
                language,
                filtered_contexts,
                context=formatter_context,
            )
        )

        source_pool = (
            contexts_for_answer
            if list_like_question_kind(working_question) is not None
            else (used_contexts if used_contexts else filtered_contexts[:top_k])
        )
        source_contexts = self.select_evidence_contexts_fn(working_question, source_pool, language, max_items=top_k)
        sources = self.formatter.build_sources_payload(
            working_question,
            source_contexts,
            language,
            context=formatter_context,
        )

        confidence_level, _ = compute_answer_confidence(filtered_contexts)

        # Append a low-confidence disclaimer when retrieval confidence is low and the
        # answer is not already a fallback. This reduces silent hallucination risk by
        # alerting users to verify the information directly with the university.
        is_fallback_answer = direct_arabic_answer in (FALLBACK_AR, FALLBACK_EN)
        if not is_fallback_answer and confidence_level == "low" and language == "ar":
            answer = answer + LOW_CONFIDENCE_NOTE_AR
        elif not is_fallback_answer and confidence_level == "low" and language != "ar":
            answer = answer + "\n\n⚠️ Note: No highly relevant source was found for this query. Please verify with the university directly."

        emit_chat_diagnostics(
            stage="answer",
            original_question=original_question,
            working_question=working_question,
            normalized_query=normalized_query,
            language=language,
            route=route,
            retrieved_contexts=contexts,
            filtered_contexts=filtered_contexts,
            source_contexts=source_contexts,
            fallback_reason="insufficient_grounded_support" if direct_arabic_answer == FALLBACK_AR else None,
            answer=answer,
        )

        return self.formatter.build_response(
            original_question,
            language,
            answer,
            sources,
            route_mode=route.mode,
            confidence=confidence_level,
            coverage=coverage_assessment,
        )


chat_service = ChatService(router=question_router, fallback_service=fallback_service, formatter=formatter)


def answer_question(question: str, top_k: int = 4) -> dict[str, Any]:
    return chat_service.answer_question(question, top_k=top_k)


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
