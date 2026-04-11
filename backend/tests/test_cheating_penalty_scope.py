"""Regression tests for cheating-penalty answer scoping.

Ensures that:
- "ما عقوبة الغش في الاختبار؟" returns exam-only penalties
  (no housing, no work/research/report/assignment items)
- "ما عقوبات الغش؟" still returns the broader set of penalties
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.chat import chat_service
from app.retrieve import normalize_for_matching

HOUSING_TERMS = ("سكن", "اسكان", "الاسكان", "الاقامه بالسكن")
NON_EXAM_TERMS = ("العمل", "البحث", "التقرير", "الواجب")


class CheatingPenaltyScopeTests(unittest.TestCase):
    def _answer(self, question: str) -> dict:
        return chat_service.answer_question(question, top_k=6)

    def test_exam_cheating_excludes_housing(self):
        response = self._answer("ما عقوبة الغش في الاختبار؟")
        answer = normalize_for_matching(response["answer"])
        for term in HOUSING_TERMS:
            self.assertNotIn(term, answer, f"Housing term '{term}' should not appear in exam-cheating answer")

    def test_exam_cheating_excludes_non_exam_items(self):
        response = self._answer("ما عقوبة الغش في الاختبار؟")
        answer = normalize_for_matching(response["answer"])
        for term in NON_EXAM_TERMS:
            self.assertNotIn(term, answer, f"Non-exam term '{term}' should not appear in exam-cheating answer")

    def test_exam_cheating_contains_exam_penalties(self):
        response = self._answer("ما عقوبة الغش في الاختبار؟")
        answer = normalize_for_matching(response["answer"])
        self.assertTrue(
            any(term in answer for term in ("الاختبار", "راسب", "حرمان")),
            "Exam-cheating answer should mention exam-related penalties",
        )

    def test_general_cheating_includes_broader_items(self):
        response = self._answer("ما عقوبات الغش؟")
        answer = normalize_for_matching(response["answer"])
        has_broader = any(term in answer for term in NON_EXAM_TERMS)
        self.assertTrue(has_broader, "General cheating answer should include work/research/report items")

    def test_general_cheating_excludes_housing(self):
        response = self._answer("ما عقوبات الغش؟")
        answer = normalize_for_matching(response["answer"])
        for term in HOUSING_TERMS:
            self.assertNotIn(term, answer, f"Housing term '{term}' should not appear in general cheating answer")

    def test_exam_cheating_no_duplicate_source_intro(self):
        response = self._answer("ما عقوبة الغش في الاختبار؟")
        answer = response["answer"]
        count = answer.count("وفق اللائحة")
        self.assertLessEqual(count, 1, f"'وفق اللائحة' appears {count} times — should appear at most once")

    def test_exam_cheating_no_duplicate_items(self):
        response = self._answer("ما عقوبة الغش في الاختبار؟")
        lines = [line.lstrip("- ").strip() for line in response["answer"].splitlines() if line.strip().startswith("-")]
        normalized = [normalize_for_matching(line) for line in lines]
        self.assertEqual(len(normalized), len(set(normalized)), f"Duplicate bullet items found: {lines}")


if __name__ == "__main__":
    unittest.main()
