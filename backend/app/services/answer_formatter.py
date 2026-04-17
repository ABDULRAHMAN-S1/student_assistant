from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class AnswerComputation:
    direct_answer: str = ""
    used_contexts: list[dict[str, Any]] = field(default_factory=list)
    unclear: bool = False


@dataclass(slots=True)
class FormatterRuntimeContext:
    fallback_ar: str
    fallback_en: str
    unclear_ar: str
    arabic_output_template: str
    english_output_template: str
    translate_to_english: Any
    polish_english_answer_text: Any
    normalize_english_status_code_meanings: Any
    context_source_type: Any
    clean_display_section: Any
    build_display_title: Any
    normalize_for_matching: Any
    source_reference_tag: Any
    context_is_partial: Any
    source_priority: Any
    parse_reference_order: Any
    extract_status_code_terms: Any
    extract_context_answer_items: Any
    append_uncertainty_note: Any
    clean_supporting_source_snippet: Any
    extract_snippet: Any
    uncertainty_note: Any
    list_like_question_kind: Any
    dedupe_preserve_order: Any
    compose_arabic_response: Any
    should_prefer_extractive_answer: Any
    format_arabic_direct_answer: Any
    select_evidence_contexts: Any
    build_status_code_arabic_answer: Any
    build_attendance_limit_arabic_answer: Any
    detect_answer_mode: Any
    build_list_like_arabic_answer: Any
    is_attendance_limit_question: Any
    is_comparison_question: Any
    polish_multiline_arabic_answer_text: Any
    polish_arabic_answer_text: Any
    contexts_have_quality_risk: Any
    apply_source_aware_arabic_wording: Any
    append_secondary_source_clarification: Any
    maybe_format_arabic_list_answer: Any
    normalize_doc_type: Any
    question: str = ""
    used_contexts: list[dict[str, Any]] = field(default_factory=list)
    unclear: bool = False
    route: Any = None
    answer_state: AnswerComputation | None = None

    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)


class AnswerFormatterService:
    def format_answer(
        self,
        raw_answer: str,
        language: str,
        sources: list[dict[str, Any]],
        context: FormatterRuntimeContext | dict[str, Any] | None = None,
    ) -> str:
        ctx = context or {}
        if raw_answer == ctx.get("fallback_ar"):
            return raw_answer if language == "ar" else ctx.get("fallback_en", raw_answer)

        if language == "ar":
            return raw_answer

        direct_arabic_answer = raw_answer
        if ctx.get("unclear") and ctx.get("unclear_ar") not in direct_arabic_answer:
            direct_arabic_answer = f"{direct_arabic_answer} {ctx['unclear_ar']}"
        direct_arabic_answer = ctx["polish_arabic_answer_text"](direct_arabic_answer)
        reference_pool = (
            sources
            if ctx["list_like_question_kind"](ctx["question"]) is not None
            else (ctx.get("used_contexts") or sources)
        )
        reference_contexts = ctx["select_evidence_contexts"](
            ctx["question"],
            reference_pool,
            language,
            max_items=3,
        )
        reference = self.build_reference(reference_contexts, "en", context=ctx)
        return self.build_english_answer(direct_arabic_answer, reference, context=ctx)

    def truncate_text(self, text: str, limit: int = 700) -> str:
        cleaned = (text or "").strip()
        if len(cleaned) <= limit:
            return cleaned
        return cleaned[: limit - 3].rstrip() + "..."

    def build_reference_entry(
        self,
        context_item: dict[str, Any],
        language: str,
        index: int,
        context: FormatterRuntimeContext | dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        ctx = context or {}
        metadata = context_item.get("metadata", {})
        doc_type = ctx["context_source_type"](context_item)
        article = (metadata.get("article", "") or "").rstrip(" :،")
        section = ctx["clean_display_section"](metadata.get("section", "")).rstrip(" :،")
        document_title = (metadata.get("document_title", "") or "").rstrip(" :،")
        title = ctx["build_display_title"](
            document_title=document_title,
            article=article,
            section=section,
            fallback_title=metadata.get("title", ""),
        ).rstrip(" :،")

        raw_parts = [document_title, article, section]
        parts: list[str] = []
        for part in raw_parts:
            if not part:
                continue
            if parts and ctx["normalize_for_matching"](parts[-1]) == ctx["normalize_for_matching"](part):
                continue
            parts.append(part)

        reference_core = "، ".join(part for part in parts if part)
        if not reference_core:
            return None

        if language == "ar":
            reference = f"{ctx['source_reference_tag'](doc_type, 'ar')} {reference_core}".strip()
        else:
            reference = f"{ctx['source_reference_tag'](doc_type, 'en')} {ctx['translate_to_english'](reference_core)}".strip()

        if ctx["context_is_partial"](context_item):
            reference = f"{reference} (نص جزئي)" if language == "ar" else f"{reference} (partial text)"

        if not reference:
            return None

        return {
            "reference": reference,
            "group_key": (
                doc_type,
                ctx["normalize_for_matching"](document_title),
                ctx["normalize_for_matching"](section),
            ),
            "source_priority": ctx["source_priority"](doc_type),
            "document_title_key": ctx["normalize_for_matching"](document_title),
            "section_key": ctx["normalize_for_matching"](section),
            "order_key": ctx["parse_reference_order"](article, title),
            "index": index,
        }

    def sort_reference_entries(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        group_order: list[tuple[str, str, str]] = []

        for entry in entries:
            group_key = entry["group_key"]
            if group_key not in grouped:
                grouped[group_key] = []
                group_order.append(group_key)
            grouped[group_key].append(entry)

        sorted_entries: list[dict[str, Any]] = []
        for group_key in group_order:
            group_entries = grouped[group_key]
            group_entries.sort(key=lambda item: (item["order_key"][0], item["order_key"][1], item["index"]))
            sorted_entries.extend(group_entries)

        return sorted_entries

    def build_reference(
        self,
        contexts: list[dict[str, Any]],
        language: str,
        context: FormatterRuntimeContext | dict[str, Any] | None = None,
    ) -> str:
        ctx = context or {}
        entries: list[dict[str, Any]] = []
        seen: set[str] = set()

        for index, context_item in enumerate(contexts):
            entry = self.build_reference_entry(context_item, language, index, context=ctx)
            if not entry:
                continue
            normalized_reference = ctx["normalize_for_matching"](entry["reference"])
            if not normalized_reference or normalized_reference in seen:
                continue
            seen.add(normalized_reference)
            entries.append(entry)

        if not entries:
            return ""

        sorted_entries = self.sort_reference_entries(entries)[:3]
        if len(sorted_entries) == 1:
            return sorted_entries[0]["reference"]

        return "\n" + "\n".join(f"- {entry['reference']}" for entry in sorted_entries)

    def build_supporting_excerpt(
        self,
        context_item: dict[str, Any],
        question: str,
        language: str,
        context: FormatterRuntimeContext | dict[str, Any] | None = None,
    ) -> str:
        ctx = context or {}
        status_codes = ctx["extract_status_code_terms"](question)
        if status_codes:
            items = ctx["extract_context_answer_items"](context_item, question, max_items=3)
            if len(items) >= 2 or len(status_codes) > 1:
                excerpt = "\n".join(f"- {item}" for item in items[: max(1, len(status_codes))])
                return ctx["append_uncertainty_note"](excerpt, language) if ctx["context_is_partial"](context_item) else excerpt
            if items:
                excerpt = items[0].strip()
                return ctx["append_uncertainty_note"](excerpt, language) if ctx["context_is_partial"](context_item) else excerpt
            if language != "ar":
                excerpt = ctx["clean_supporting_source_snippet"](ctx["extract_snippet"](context_item, question, "ar"))
                return ctx["append_uncertainty_note"](excerpt, language) if ctx["context_is_partial"](context_item) else excerpt
            return ctx["uncertainty_note"](language) if ctx["context_is_partial"](context_item) else ""

        if language != "ar":
            return ctx["clean_supporting_source_snippet"](ctx["extract_snippet"](context_item, question, language))

        items = ctx["extract_context_answer_items"](context_item, question, max_items=3)
        if ctx["list_like_question_kind"](question) is not None:
            if len(items) >= 2:
                excerpt = "\n".join(f"- {item}" for item in items)
                return ctx["append_uncertainty_note"](excerpt, language) if ctx["context_is_partial"](context_item) else excerpt
            if items:
                excerpt = " ".join(ctx["dedupe_preserve_order"](items[:2])).strip()
                return ctx["append_uncertainty_note"](excerpt, language) if ctx["context_is_partial"](context_item) else excerpt
            excerpt = ctx["clean_supporting_source_snippet"](ctx["extract_snippet"](context_item, question, language))
            if not excerpt and ctx["context_is_partial"](context_item):
                return ctx["uncertainty_note"](language)
            return ctx["append_uncertainty_note"](excerpt, language) if ctx["context_is_partial"](context_item) else excerpt
        if items:
            excerpt = " ".join(ctx["dedupe_preserve_order"](items[:2])).strip()
            return ctx["append_uncertainty_note"](excerpt, language) if ctx["context_is_partial"](context_item) else excerpt
        excerpt = ctx["clean_supporting_source_snippet"](ctx["extract_snippet"](context_item, question, language))
        if not excerpt and ctx["context_is_partial"](context_item):
            return ctx["uncertainty_note"](language)
        return ctx["append_uncertainty_note"](excerpt, language) if ctx["context_is_partial"](context_item) else excerpt

    def build_english_answer(
        self,
        arabic_answer: str,
        reference: str,
        context: FormatterRuntimeContext | dict[str, Any] | None = None,
    ) -> str:
        ctx = context or {}
        direct_answer = ctx["translate_to_english"](arabic_answer) if arabic_answer else ctx["fallback_en"]
        if not direct_answer:
            direct_answer = ctx["fallback_en"]
        direct_answer = ctx["polish_english_answer_text"](direct_answer)
        direct_answer = ctx["normalize_english_status_code_meanings"](direct_answer)
        if reference:
            return ctx["english_output_template"].format(direct_answer=direct_answer, reference=reference).strip()
        return direct_answer

    def build_arabic_answer(
        self,
        question: str,
        contexts: list[dict[str, Any]],
        context: FormatterRuntimeContext | dict[str, Any] | None = None,
    ) -> str:
        ctx = context or {}
        answer_state = ctx.get("answer_state")
        if answer_state is not None:
            direct_answer = answer_state.direct_answer
            used_contexts = answer_state.used_contexts
            unclear = answer_state.unclear
        else:
            direct_answer, used_contexts, unclear = ctx["compose_arabic_response"](question, contexts)
        if direct_answer == ctx["fallback_ar"]:
            return direct_answer

        route = ctx.get("route")
        mode = route.mode if route is not None else ctx["detect_answer_mode"](question, "ar")
        is_attendance_limit = (
            bool(getattr(route, "is_attendance_limit", False))
            if route is not None
            else ctx["is_attendance_limit_question"](question)
        )

        if unclear and ctx["unclear_ar"] not in direct_answer:
            direct_answer = f"{direct_answer} {ctx['unclear_ar']}"
        answer_contexts = used_contexts if used_contexts else contexts
        if ctx["should_prefer_extractive_answer"](question, answer_contexts, unclear=unclear):
            direct_answer = ctx["format_arabic_direct_answer"](question, direct_answer, answer_contexts)
            reference_contexts = ctx["select_evidence_contexts"](question, answer_contexts, "ar", max_items=3)
            reference = self.build_reference(reference_contexts, "ar", context=ctx)
            if reference:
                return ctx["arabic_output_template"].format(direct_answer=direct_answer, reference=reference).strip()
            return direct_answer

        structuring_contexts = (
            contexts
            if ctx["list_like_question_kind"](question) is not None or ctx["is_attendance_limit_question"](question)
            else answer_contexts
        )
        structured_answer = (
            ctx["build_status_code_arabic_answer"](question, structuring_contexts)
            or ctx["build_attendance_limit_arabic_answer"](question, structuring_contexts)
            or (
                None
                if mode == "attendance_penalty"
                else ctx["build_list_like_arabic_answer"](question, structuring_contexts)
            )
        )
        direct_answer = structured_answer or ctx["format_arabic_direct_answer"](question, direct_answer, answer_contexts)
        if ctx["is_comparison_question"](question):
            direct_answer = "\n".join(
                ctx["dedupe_preserve_order"]([line for line in direct_answer.splitlines() if line.strip()])
            )
        else:
            if "\n-" in direct_answer:
                direct_answer = ctx["polish_multiline_arabic_answer_text"](direct_answer)
            else:
                direct_answer = ctx["polish_arabic_answer_text"](direct_answer)
            if not ctx["contexts_have_quality_risk"](answer_contexts):
                direct_answer = ctx["apply_source_aware_arabic_wording"](question, direct_answer, answer_contexts)
            if mode == "general" and "\n-" not in direct_answer and not unclear:
                direct_answer = ctx["append_secondary_source_clarification"](question, direct_answer, answer_contexts)
            if "\n-" not in direct_answer:
                direct_answer = ctx["maybe_format_arabic_list_answer"](direct_answer)

        reference_pool = answer_contexts if ctx["list_like_question_kind"](question) is None else contexts
        reference_contexts = ctx["select_evidence_contexts"](question, reference_pool, "ar", max_items=3)
        reference = self.build_reference(reference_contexts, "ar", context=ctx)
        if reference:
            return ctx["arabic_output_template"].format(direct_answer=direct_answer, reference=reference).strip()
        return direct_answer

    def build_source_label(self, item: dict[str, Any], context: "FormatterRuntimeContext | dict[str, Any] | None" = None) -> str:
        """Build a concise, human-readable label for a source item.

        Format: [نوع المصدر] اسم الوثيقة — المادة X / القسم Y
        This label is shown in the UI next to each retrieved source.
        """
        ctx = context or {}
        metadata = item.get("metadata", {})
        normalize_fn = ctx.get("normalize_doc_type") if ctx else None
        doc_type = normalize_fn(metadata.get("doc_type", "regulation")) if callable(normalize_fn) else metadata.get("doc_type", "regulation")
        document_title = (metadata.get("document_title") or "").strip().rstrip(" :،")
        article = (metadata.get("article") or "").strip().rstrip(" :،")
        section = (metadata.get("section") or "").strip().rstrip(" :،")

        type_labels = {"regulation": "لائحة", "policy": "سياسة", "guide": "دليل", "faq": "أسئلة شائعة"}
        type_label = type_labels.get(doc_type, "مصدر")

        parts = []
        if document_title:
            parts.append(document_title)
        if article and article != document_title:
            parts.append(article)
        if section and section not in (document_title, article):
            parts.append(section)

        core = " — ".join(parts) if parts else ""
        return f"[{type_label}] {core}".strip() if core else f"[{type_label}]"

    def build_sources_payload(
        self,
        question: str,
        source_contexts: list[dict[str, Any]],
        language: str,
        context: "FormatterRuntimeContext | dict[str, Any] | None" = None,
    ) -> list[dict[str, Any]]:
        ctx = context or {}
        payload: list[dict[str, Any]] = []
        for item in source_contexts:
            excerpt = self.build_supporting_excerpt(item, question, language, context=ctx)
            if not excerpt.strip():
                continue
            score = float(item.get("score", 0.0))
            payload.append(
                {
                    "id": item["id"],
                    "source": item["metadata"].get("source"),
                    "doc_type": ctx["normalize_doc_type"](item["metadata"].get("doc_type", "regulation")),
                    "document_title": item["metadata"].get("document_title"),
                    "section": item["metadata"].get("section"),
                    "article": item["metadata"].get("article"),
                    "title": item["metadata"].get("title"),
                    "score": score,
                    "content": excerpt,
                    "content_preview": self.truncate_text(excerpt, 260),
                    "label": self.build_source_label(item, context=ctx),
                }
            )
        return payload

    def build_response(
        self,
        question: str,
        language: str,
        answer: str,
        sources: list[dict[str, Any]],
        route_mode: str = "",
        confidence: str = "medium",
        coverage: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        response = {
            "question": question,
            "language": language,
            "answer": answer,
            "sources": sources,
            "route_mode": route_mode,
            "confidence": confidence,
        }
        if coverage is not None:
            response["coverage"] = coverage
        return response