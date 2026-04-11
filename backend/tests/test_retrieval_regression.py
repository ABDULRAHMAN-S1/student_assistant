"""Retrieval regression tests.

Validates that the search layer (embeddings + vector store + ranking)
returns relevant chunks for known question categories.  These tests
act as a safety-net: if the vector DB, embedding model, or scoring
logic changes, failures here surface the regression immediately.

Each test asserts that at least one top-k result contains expected
content or metadata — not that the answer is formatted correctly
(that's covered by test_cheating_penalty_scope and test_chat_service).
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.chat import search, normalize_for_matching


def _haystack(ctx: dict) -> str:
    """Combine content + key metadata into a single searchable string."""
    meta = ctx.get("metadata", {})
    parts = [
        ctx.get("content", ""),
        meta.get("document_title", ""),
        meta.get("section", ""),
        meta.get("article", ""),
    ]
    return normalize_for_matching(" ".join(p for p in parts if p))


class RetrievalRegressionTests(unittest.TestCase):
    """Ensure search() returns at least one relevant chunk for key domains."""

    # ------------------------------------------------------------------
    # Penalty / Cheating
    # ------------------------------------------------------------------
    def test_cheating_penalty_returns_discipline_rules(self):
        results = search("ما عقوبة الغش في الاختبار؟", top_k=6)
        self.assertTrue(results, "search returned no results")
        haystacks = [_haystack(r) for r in results]
        self.assertTrue(
            any("العقوبات" in h and "الماده الثامنه" in h for h in haystacks),
            "Expected a chunk from Article 8 (discipline penalties) in top results",
        )

    # ------------------------------------------------------------------
    # Withdrawal
    # ------------------------------------------------------------------
    def test_withdrawal_returns_relevant_article(self):
        results = search("هل يمكنني الانسحاب من مادة؟", top_k=6)
        self.assertTrue(results, "search returned no results")
        haystacks = [_haystack(r) for r in results]
        self.assertTrue(
            any("انسحاب" in h or "الانسحاب" in h for h in haystacks),
            "Expected a chunk mentioning withdrawal in top results",
        )

    # ------------------------------------------------------------------
    # Attendance / Absence
    # ------------------------------------------------------------------
    def test_absence_returns_attendance_rules(self):
        results = search("كم نسبة الغياب المسموح بها؟", top_k=6)
        self.assertTrue(results, "search returned no results")
        haystacks = [_haystack(r) for r in results]
        self.assertTrue(
            any("غياب" in h or "غايب" in h or "حضور" in h for h in haystacks),
            "Expected a chunk about attendance/absence in top results",
        )

    # ------------------------------------------------------------------
    # Grading system
    # ------------------------------------------------------------------
    def test_grading_returns_grade_related_chunk(self):
        results = search("ما هي التقديرات في الجامعة؟", top_k=6)
        self.assertTrue(results, "search returned no results")
        haystacks = [_haystack(r) for r in results]
        self.assertTrue(
            any("التقديرات" in h or "تقدير" in h for h in haystacks),
            "Expected a chunk about grading/grades in top results",
        )

    # ------------------------------------------------------------------
    # Academic load
    # ------------------------------------------------------------------
    def test_load_limit_returns_credit_hours_chunk(self):
        results = search("كم الحد الأعلى للساعات في الفصل؟", top_k=6)
        self.assertTrue(results, "search returned no results")
        haystacks = [_haystack(r) for r in results]
        self.assertTrue(
            any("العبء الدراسي" in h or "الحد الاعلي" in h or "ساع" in h for h in haystacks),
            "Expected a chunk about academic load / credit hours in top results",
        )

    # ------------------------------------------------------------------
    # Missed final exam
    # ------------------------------------------------------------------
    def test_missed_final_returns_exam_absence_chunk(self):
        results = search("ماذا يحدث إذا غبت عن الاختبار النهائي؟", top_k=6)
        self.assertTrue(results, "search returned no results")
        haystacks = [_haystack(r) for r in results]
        self.assertTrue(
            any(("غايب" in h or "غاب" in h or "غبت" in h) and "الاختبار" in h for h in haystacks),
            "Expected a chunk about missing a final exam in top results",
        )

    # ------------------------------------------------------------------
    # Result structure
    # ------------------------------------------------------------------
    def test_search_result_has_required_fields(self):
        results = search("ما عقوبة الغش؟", top_k=4)
        self.assertTrue(results, "search returned no results")
        for r in results:
            self.assertIn("id", r)
            self.assertIn("content", r)
            self.assertIn("metadata", r)
            self.assertIsInstance(r["metadata"], dict)
            self.assertIn("score", r)

    def test_search_respects_top_k(self):
        for k in (2, 4, 8):
            results = search("عقوبة الغش", top_k=k)
            self.assertLessEqual(len(results), k, f"search(top_k={k}) returned more than {k} results")

    def test_empty_query_returns_empty(self):
        self.assertEqual(search("", top_k=4), [])
        self.assertEqual(search("   ", top_k=4), [])


if __name__ == "__main__":
    unittest.main()
