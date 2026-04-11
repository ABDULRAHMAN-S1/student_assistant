from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.chat import FALLBACK_AR, ChatService, RouteDecision, filter_contexts_for_generation
from app.retrieve import normalize_for_matching
from app.services.answer_formatter import AnswerFormatterService


class RecordingRouter:
    def __init__(self, route: dict[str, Any], *, is_attendance_limit: bool = False) -> None:
        self.route = route
        self.is_attendance_limit = is_attendance_limit
        self.route_calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self.attendance_limit_calls: list[str] = []

    def route_question(self, question: str, context: dict[str, Any] | None = None, *, language: str) -> dict[str, Any]:
        self.route_calls.append((question, language, context))
        return dict(self.route)

    def is_attendance_limit_question(self, question: str) -> bool:
        self.attendance_limit_calls.append(question)
        return self.is_attendance_limit


class RecordingFallbackService:
    def __init__(self, fallback_contexts: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.fallback_contexts = fallback_contexts or {}
        self.calls: list[tuple[str, str | None, int]] = []

    def get_fallback_context(self, mode: str, *, question: str | None = None, limit: int = 0) -> list[dict[str, Any]]:
        self.calls.append((mode, question, limit))
        return list(self.fallback_contexts.get(mode, []))

    def context_search_text(self, context: dict[str, Any]) -> str:
        metadata = context.get("metadata", {})
        parts = [
            metadata.get("article", ""),
            metadata.get("section", ""),
            metadata.get("document_title", ""),
            context.get("content", ""),
        ]
        return normalize_for_matching(" ".join(part for part in parts if part))

    def asks_upper_limit(self, normalized_question: str) -> bool:
        return False

    def asks_lower_limit(self, normalized_question: str) -> bool:
        return False

    def attendance_query_terms(self, question: str) -> list[str]:
        return []

    def context_attendance_match_count(self, context: dict[str, Any], question_terms: list[str]) -> int:
        return 0


class RecordingFormatter:
    def __init__(self) -> None:
        self.build_arabic_answer_calls: list[tuple[str, list[dict[str, Any]], Any]] = []
        self.format_answer_calls: list[tuple[str, str, list[dict[str, Any]], Any]] = []
        self.build_sources_calls: list[tuple[str, list[dict[str, Any]], str, Any]] = []

    def build_arabic_answer(self, question: str, contexts: list[dict[str, Any]], *, context: Any) -> str:
        self.build_arabic_answer_calls.append((question, contexts, context))
        return "إجابة عربية منسقة"

    def format_answer(self, raw_answer: str, language: str, sources: list[dict[str, Any]], *, context: Any) -> str:
        self.format_answer_calls.append((raw_answer, language, sources, context))
        return "Formatted English Answer"

    def build_sources_payload(
        self,
        question: str,
        source_contexts: list[dict[str, Any]],
        language: str,
        *,
        context: Any,
    ) -> list[dict[str, Any]]:
        self.build_sources_calls.append((question, source_contexts, language, context))
        return [{"id": item["id"], "content": item.get("content", "")} for item in source_contexts]

    def build_response(self, question: str, language: str, answer: str, sources: list[dict[str, Any]], *, route_mode: str = "") -> dict[str, Any]:
        return {
            "question": question,
            "language": language,
            "answer": answer,
            "sources": sources,
            "route_mode": route_mode,
        }


class ChatServiceTests(unittest.TestCase):
    def make_context(self, context_id: str, content: str) -> dict[str, Any]:
        return {
            "id": context_id,
            "metadata": {
                "doc_type": "regulation",
                "document_title": "لائحة الدراسة والاختبارات",
                "section": "الانسحاب",
                "article": "المادة السابعة عشرة",
                "title": "البند 1",
            },
            "score": 0.95,
            "lexical_score": 0.9,
            "content": content,
        }

    def test_arabic_pipeline_uses_formatter_as_single_answer_owner(self) -> None:
        router = RecordingRouter({"mode": "withdrawal", "fallback_mode": "withdrawal", "uses_fallback_flow": True})
        fallback_service = RecordingFallbackService()
        formatter = RecordingFormatter()
        filter_calls: list[RouteDecision] = []
        contexts = [self.make_context("ctx-1", "يجوز للطالب الانسحاب من المقرر.")]

        def filter_fn(
            question: str,
            raw_contexts: list[dict[str, Any]],
            language: str,
            *,
            route: RouteDecision,
            fallback_service: RecordingFallbackService,
        ) -> list[dict[str, Any]]:
            filter_calls.append(route)
            return raw_contexts

        service = ChatService(
            router=router,
            fallback_service=fallback_service,
            formatter=formatter,
            search_fn=lambda query, top_k: contexts,
            detect_language_fn=lambda question: "ar",
            rewrite_query_fn=lambda question: question,
            filter_contexts_fn=filter_fn,
            compose_arabic_response_fn=lambda question, filtered: ("إجابة مباشرة", filtered, False),
            select_evidence_contexts_fn=lambda question, source_pool, language, max_items: source_pool[:max_items],
        )

        response = service.answer_question("هل أقدر أنسحب من المادة؟", top_k=4)

        self.assertEqual(len(router.route_calls), 1)
        self.assertEqual(len(filter_calls), 1)
        self.assertIsInstance(filter_calls[0], RouteDecision)
        self.assertEqual(filter_calls[0].mode, "withdrawal")
        self.assertEqual(len(formatter.build_arabic_answer_calls), 1)
        self.assertEqual(len(formatter.format_answer_calls), 0)
        self.assertEqual(response["answer"], "إجابة عربية منسقة")
        self.assertEqual(response["language"], "ar")

    def test_english_pipeline_uses_format_answer_without_arabic_rebuild(self) -> None:
        router = RecordingRouter({"mode": "general", "fallback_mode": None, "uses_fallback_flow": False})
        fallback_service = RecordingFallbackService()
        formatter = RecordingFormatter()
        contexts = [self.make_context("ctx-1", "يجوز للطالب الانسحاب من المقرر.")]
        search_calls: list[int] = []

        service = ChatService(
            router=router,
            fallback_service=fallback_service,
            formatter=formatter,
            search_fn=lambda query, top_k: search_calls.append(top_k) or contexts,
            detect_language_fn=lambda question: "en",
            rewrite_query_fn=lambda question: question,
            filter_contexts_fn=lambda question, raw_contexts, language, *, route, fallback_service: raw_contexts,
            compose_arabic_response_fn=lambda question, filtered: ("اجابة عربية", filtered, False),
            select_evidence_contexts_fn=lambda question, source_pool, language, max_items: source_pool[:max_items],
        )

        response = service.answer_question("withdraw from course", top_k=4)

        self.assertEqual(search_calls, [8])
        self.assertEqual(len(formatter.build_arabic_answer_calls), 0)
        self.assertEqual(len(formatter.format_answer_calls), 1)
        self.assertEqual(response["answer"], "Formatted English Answer")
        self.assertEqual(response["language"], "en")

    def test_penalty_route_expands_retrieval_top_k_once(self) -> None:
        router = RecordingRouter({"mode": "penalty", "fallback_mode": "penalty", "uses_fallback_flow": True})
        fallback_service = RecordingFallbackService()
        formatter = RecordingFormatter()
        search_calls: list[int] = []
        contexts = [self.make_context("ctx-1", "عقوبة الغش في الاختبار النهائي.")]

        service = ChatService(
            router=router,
            fallback_service=fallback_service,
            formatter=formatter,
            search_fn=lambda query, top_k: search_calls.append(top_k) or contexts,
            detect_language_fn=lambda question: "ar",
            rewrite_query_fn=lambda question: question,
            filter_contexts_fn=lambda question, raw_contexts, language, *, route, fallback_service: raw_contexts,
            compose_arabic_response_fn=lambda question, filtered: ("إجابة مباشرة", filtered, False),
            select_evidence_contexts_fn=lambda question, source_pool, language, max_items: source_pool[:max_items],
        )

        service.answer_question("وش عقوبة الغش؟", top_k=4)

        self.assertEqual(search_calls, [12])
        self.assertEqual(len(router.route_calls), 1)

    def test_filter_contexts_applies_withdrawal_fallback_once(self) -> None:
        fallback_context = self.make_context("fallback-1", "يجوز للطالب الانسحاب من المقرر خلال المدة المحددة.")
        fallback_service = RecordingFallbackService({"withdrawal": [fallback_context]})
        contexts = [self.make_context("ctx-1", "يجوز للطالب الانسحاب من المقرر.")]
        route = RouteDecision(
            mode="withdrawal",
            fallback_mode="withdrawal",
            uses_fallback_flow=True,
            retrieval_top_k=8,
            is_attendance_limit=False,
        )

        filtered = filter_contexts_for_generation(
            "هل أقدر أنسحب من المادة؟",
            contexts,
            "ar",
            route=route,
            fallback_service=fallback_service,
        )

        self.assertTrue(filtered)
        self.assertEqual(
            [call for call in fallback_service.calls if call[0] == "withdrawal"],
            [("withdrawal", None, 4)],
        )

    def test_filter_contexts_rejects_unrelated_lecture_recording_contexts(self) -> None:
        fallback_service = RecordingFallbackService()
        attendance_context = self.make_context(
            "ctx-1",
            "يجوز لمجلس الكلية أو المعهد رفع الحرمان والسماح للطالب بدخول الاختبار النهائي إذا قُبل العذر.",
        )
        attendance_context["metadata"]["section"] = "الحضور والحرمان"
        attendance_context["metadata"]["article"] = "المادة الخامسة عشرة"

        schedule_context = self.make_context(
            "ctx-2",
            "تلتزم الكلية بعقد الاختبار النصفي في موعد المحاضرة المعتاد مع إعلان المواعيد عبر النظام.",
        )
        schedule_context["metadata"]["section"] = "مواعيد الاختبارات"
        schedule_context["metadata"]["article"] = "٢-٤"

        route = RouteDecision(
            mode="lecture_recording",
            fallback_mode="lecture_recording",
            uses_fallback_flow=True,
            retrieval_top_k=8,
            is_attendance_limit=False,
        )

        filtered = filter_contexts_for_generation(
            "هل يسمح بتصوير المحاضرات؟",
            [attendance_context, schedule_context],
            "ar",
            route=route,
            fallback_service=fallback_service,
        )

        self.assertEqual(filtered, [])

    def test_filter_contexts_keeps_broad_general_context_with_strong_semantic_support(self) -> None:
        fallback_service = RecordingFallbackService()
        general_context = {
            "id": "ctx-general-1",
            "metadata": {
                "doc_type": "regulation",
                "document_title": "لائحة الدراسة والاختبارات للمرحلة الجامعية",
                "section": "الفصل الحادي عشر: أحكام عامة",
                "article": "المادة التاسعة والأربعون",
                "title": "المادة التاسعة والأربعون",
            },
            "score": 0.9182,
            "lexical_score": 0.0,
            "semantic_score": 0.7982,
            "content": "مع مراعاة ما يصدر من الجهات المختصة، للجامعة إتاحة الفرصة لطلاب المرحلة الثانوية وفق ما تنص عليه اللائحة المعتمدة.",
        }
        route = RouteDecision(
            mode="general",
            fallback_mode=None,
            uses_fallback_flow=False,
            retrieval_top_k=8,
            is_attendance_limit=False,
        )

        filtered = filter_contexts_for_generation(
            "ما هي لوائح الجامعة؟",
            [general_context],
            "ar",
            route=route,
            fallback_service=fallback_service,
        )

        self.assertEqual([context["id"] for context in filtered], ["ctx-general-1"])

    def test_answer_question_keeps_general_semantic_context_out_of_fallback(self) -> None:
        router = RecordingRouter({"mode": "general", "fallback_mode": None, "uses_fallback_flow": False})
        fallback_service = RecordingFallbackService()
        formatter = AnswerFormatterService()
        general_context = {
            "id": "ctx-general-live-1",
            "metadata": {
                "doc_type": "regulation",
                "document_title": "لائحة الدراسة والاختبارات للمرحلة الجامعية",
                "section": "الفصل الحادي عشر: أحكام عامة",
                "article": "المادة التاسعة والأربعون",
                "title": "المادة التاسعة والأربعون",
                "status": "complete",
            },
            "score": 0.9182,
            "lexical_score": 0.0,
            "semantic_score": 0.7982,
            "content": "هذه اللائحة تنظم الدراسة والاختبارات في الجامعة، وتحدد الأحكام العامة والإجراءات الأكاديمية المعتمدة للطلاب والبرامج الدراسية.",
        }
        service = ChatService(
            router=router,
            fallback_service=fallback_service,
            formatter=formatter,
            search_fn=lambda query, top_k: [general_context],
            detect_language_fn=lambda question: "ar",
            rewrite_query_fn=lambda question: question,
        )

        response = service.answer_question("ما هي لوائح الجامعة؟", top_k=4)

        self.assertNotEqual(response["answer"], FALLBACK_AR)
        self.assertTrue(response["sources"])
        self.assertEqual(response["sources"][0]["id"], "ctx-general-live-1")


if __name__ == "__main__":
    unittest.main()
