from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.retrieve import light_stem, normalize_for_matching, search, tokenize_text


def _make_record(
    *,
    record_id: str,
    doc_type: str,
    document_title: str,
    section: str,
    article: str,
    content: str,
):
    metadata = {
        "doc_type": doc_type,
        "document_title": document_title,
        "section": section,
        "article": article,
        "title": document_title,
        "source": "test.txt",
        "language": "ar",
        "status": "complete",
        "qa_flags": [],
    }
    metadata_text = " ".join([document_title, section, article]).strip()
    return {
        "id": record_id,
        "content": content,
        "metadata": metadata,
        "normalized_content": normalize_for_matching(content),
        "normalized_metadata": normalize_for_matching(metadata_text),
        "content_stems": {light_stem(t) for t in tokenize_text(content)},
        "metadata_stems": {light_stem(t) for t in tokenize_text(metadata_text)},
        "duplicate_content_count": 0,
    }


class FaqRetrievalPreferenceTests(unittest.TestCase):
    def test_strong_faq_like_query_can_retrieve_faq_doc_type(self) -> None:
        faq = _make_record(
            record_id="faq-1",
            doc_type="faq",
            document_title="أسئلة شائعة - القبول",
            section="الأسئلة الشائعة",
            article="سؤال: كيف يتم القبول؟",
            content="سؤال: كيف يتم القبول؟\nالجواب: يتم القبول عبر بوابة القبول حسب الشروط المعلنة.",
        )
        reg = _make_record(
            record_id="reg-1",
            doc_type="regulation",
            document_title="لائحة الدراسة والاختبارات",
            section="القبول",
            article="المادة الأولى",
            content="يخضع القبول للضوابط العامة المعتمدة.",
        )
        record_map = {faq["id"]: faq, reg["id"]: reg}

        def lexical_search_stub(query: str, top_k: int = 4, query_profile=None):
            # Simulate a strong lexical hit for the FAQ.
            return [
                {"id": "faq-1", "content": faq["content"], "metadata": faq["metadata"], "score": 0.92},
                {"id": "reg-1", "content": reg["content"], "metadata": reg["metadata"], "score": 0.55},
            ][:top_k]

        with patch("app.retrieve.get_chunk_record_map", return_value=record_map), patch(
            "app.retrieve.semantic_search", return_value=[]
        ), patch("app.retrieve.lexical_search", side_effect=lexical_search_stub):
            results = search("كيف يتم القبول؟", top_k=4)
            self.assertTrue(results, "search returned no results")
            self.assertTrue(
                any((r.get("metadata", {}) or {}).get("doc_type") == "faq" for r in results),
                "Expected at least one FAQ result when a strong FAQ-like match exists",
            )

    def test_explicit_faq_query_prefers_faq_when_close_match(self) -> None:
        faq = _make_record(
            record_id="faq-2",
            doc_type="faq",
            document_title="أسئلة شائعة - الانسحاب",
            section="الأسئلة الشائعة",
            article="سؤال: هل أقدر أنسحب؟",
            content="سؤال: هل أقدر أنسحب من مقرر؟\nالجواب: نعم، وفق الشروط المحددة في اللائحة.",
        )
        reg = _make_record(
            record_id="reg-2",
            doc_type="regulation",
            document_title="لائحة الدراسة والاختبارات",
            section="الانسحاب",
            article="المادة السابعة عشرة",
            content="يجوز للطالب الانسحاب من مقرر خلال المدة المحددة.",
        )
        record_map = {faq["id"]: faq, reg["id"]: reg}

        def lexical_search_stub(query: str, top_k: int = 4, query_profile=None):
            # Make regulation slightly higher lexically so preference must matter.
            return [
                {"id": "reg-2", "content": reg["content"], "metadata": reg["metadata"], "score": 0.88},
                {"id": "faq-2", "content": faq["content"], "metadata": faq["metadata"], "score": 0.84},
            ][:top_k]

        with patch("app.retrieve.get_chunk_record_map", return_value=record_map), patch(
            "app.retrieve.semantic_search", return_value=[]
        ), patch("app.retrieve.lexical_search", side_effect=lexical_search_stub):
            results = search("FAQ: هل أقدر أنسحب من مقرر؟", top_k=2)
            self.assertTrue(results, "search returned no results")
            self.assertEqual((results[0].get("metadata", {}) or {}).get("doc_type"), "faq")


if __name__ == "__main__":
    unittest.main()

