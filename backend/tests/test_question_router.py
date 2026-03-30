from __future__ import annotations

import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.chat_fallbacks import FallbackService
from app.routing.question_router import QuestionRouter


class QuestionRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.router = QuestionRouter(fallback_service=FallbackService())

    def assert_route(
        self,
        question: str,
        *,
        expected_mode: str,
        expected_fallback_mode: str | None = None,
        expected_uses_fallback_flow: bool = False,
        language: str = "ar",
    ) -> None:
        route = self.router.route_question(question, language=language)
        self.assertEqual(route["mode"], expected_mode, msg=question)
        self.assertEqual(route["fallback_mode"], expected_fallback_mode, msg=question)
        self.assertEqual(route["uses_fallback_flow"], expected_uses_fallback_flow, msg=question)

    def test_attendance_and_absence_questions(self) -> None:
        cases = [
            ("كم نسبة الحضور؟", "general", "attendance", True),
            ("هل ممكن أعتذر عن الغياب؟", "general", "attendance", True),
            ("هل الحرمان له علاقة بالاختبار النهائي؟", "general", "attendance", True),
        ]
        for question, expected_mode, expected_fallback_mode, expected_uses_fallback in cases:
            with self.subTest(question=question):
                self.assert_route(
                    question,
                    expected_mode=expected_mode,
                    expected_fallback_mode=expected_fallback_mode,
                    expected_uses_fallback_flow=expected_uses_fallback,
                )

    def test_withdrawal_questions_and_variations(self) -> None:
        cases = [
            "هل أقدر أنسحب من المادة؟",
            "وش شروط الانسحاب؟",
            "انسحاب؟",
            "اقدر احذف مادة؟",
        ]
        for question in cases:
            with self.subTest(question=question):
                self.assert_route(
                    question,
                    expected_mode="withdrawal",
                    expected_fallback_mode="withdrawal",
                    expected_uses_fallback_flow=True,
                )

        self.assert_route(
            "withdraw من المادة",
            expected_mode="withdrawal",
            expected_fallback_mode=None,
            expected_uses_fallback_flow=False,
        )

    def test_gpa_and_grading_questions(self) -> None:
        cases = [
            ("كيف أحسب المعدل؟", "gpa_formula"),
            ("كيف احتساب المعدل التراكمي؟", "gpa_formula"),
            ("كم أحتاج أجيب عشان أرفع معدلي؟", "general"),
        ]
        for question, expected_mode in cases:
            with self.subTest(question=question):
                self.assert_route(question, expected_mode=expected_mode)

    def test_admission_and_requirement_questions(self) -> None:
        cases = [
            ("وش شروط القبول؟", "admission_conditions"),
            ("ما متطلبات القبول؟", "admission_conditions"),
            ("هل أقدر أدخل التخصص هذا؟", "general"),
        ]
        for question, expected_mode in cases:
            with self.subTest(question=question):
                self.assert_route(question, expected_mode=expected_mode)

    def test_missed_final_and_penalty_questions(self) -> None:
        cases = [
            ("غيبت عن الاختبار النهائي وش يصير؟", "general", None, False),
            ("غيبت عن الاختبار النهايي وش يصير؟", "general", None, False),
            ("هل فيه خصم درجات؟", "general", None, False),
            ("وش عقوبة الغش؟", "penalty", "penalty", True),
        ]
        for question, expected_mode, expected_fallback_mode, expected_uses_fallback in cases:
            with self.subTest(question=question):
                self.assert_route(
                    question,
                    expected_mode=expected_mode,
                    expected_fallback_mode=expected_fallback_mode,
                    expected_uses_fallback_flow=expected_uses_fallback,
                )

    def test_general_questions(self) -> None:
        for question in ("ما هو الذكاء الاصطناعي؟", "اشرح لي بايثون", "وش يصير؟"):
            with self.subTest(question=question):
                self.assert_route(question, expected_mode="general")

    def test_housing_and_lecture_recording_categories(self) -> None:
        cases = [
            ("وش شروط السكن؟", "housing_conditions", "housing_conditions", True),
            ("هل يسمح تصوير المحاضرات؟", "lecture_recording", "lecture_recording", True),
        ]
        for question, expected_mode, expected_fallback_mode, expected_uses_fallback in cases:
            with self.subTest(question=question):
                self.assert_route(
                    question,
                    expected_mode=expected_mode,
                    expected_fallback_mode=expected_fallback_mode,
                    expected_uses_fallback_flow=expected_uses_fallback,
                )

    def test_mixed_language_and_short_question_edge_cases(self) -> None:
        cases = [
            ("missed final اختبار", "missed_final", None, False),
            ("withdraw?", "withdrawal", None, False),
            ("غيبت final exam", "general", None, False),
        ]
        for question, expected_mode, expected_fallback_mode, expected_uses_fallback in cases:
            with self.subTest(question=question):
                self.assert_route(
                    question,
                    expected_mode=expected_mode,
                    expected_fallback_mode=expected_fallback_mode,
                    expected_uses_fallback_flow=expected_uses_fallback,
                )

    def test_non_arabic_language_forces_general_mode(self) -> None:
        self.assert_route(
            "withdraw from course",
            expected_mode="general",
            expected_fallback_mode=None,
            expected_uses_fallback_flow=False,
            language="en",
        )


if __name__ == "__main__":
    unittest.main()