from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app.chat import FALLBACK_AR, answer_question
from app.retrieve import normalize_for_matching, search


RAW_DIR = BACKEND_ROOT / "data" / "raw"
MANIFEST_PATH = BACKEND_ROOT / "data" / "processed" / "manifest.json"


def text_hash(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ChatRelevanceRegressionTests(unittest.TestCase):
    def test_processed_manifest_matches_current_raw_hashes(self) -> None:
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        manifest_documents = {document["source_file"]: document for document in manifest.get("documents", [])}
        raw_files = sorted(path for path in RAW_DIR.iterdir() if path.is_file() and path.suffix.lower() == ".txt")

        self.assertEqual(set(manifest_documents), {path.name for path in raw_files})

        for path in raw_files:
            with self.subTest(source_file=path.name):
                self.assertEqual(manifest_documents[path.name]["source_hash"], text_hash(path))

    def test_search_prefers_explicit_lecture_recording_rule(self) -> None:
        results = search("هل يسمح بتصوير المحاضرات؟", top_k=5)

        self.assertTrue(results)
        first_result = results[0]
        first_content = normalize_for_matching(first_result["content"])
        first_title = normalize_for_matching(first_result["metadata"].get("document_title", ""))

        self.assertIn("قواعد السلوك والانضباط الطلابي", first_title)
        self.assertIn("تصوير", first_content)
        self.assertIn("موافقه المحاضر", first_content)

    def test_lecture_recording_answer_uses_explicit_source(self) -> None:
        response = answer_question("هل يسمح بتصوير المحاضرات؟", top_k=4)
        normalized_answer = normalize_for_matching(response["answer"])

        self.assertNotEqual(response["answer"], FALLBACK_AR)
        self.assertIn("تصوير", normalized_answer)
        self.assertIn("موافقه المحاضر", normalized_answer)
        self.assertTrue(response["sources"])
        self.assertIn(
            "قواعد السلوك والانضباط الطلابي",
            normalize_for_matching(response["sources"][0].get("document_title", "")),
        )
        self.assertIn("الماده الخامسه", normalize_for_matching(response["sources"][0].get("article", "")))

    def test_cheating_penalty_answer_stays_in_cheating_domain(self) -> None:
        response = answer_question("ما عقوبة الغش في الاختبار؟", top_k=4)
        normalized_answer = normalize_for_matching(response["answer"])
        normalized_titles = [normalize_for_matching(source.get("document_title", "")) for source in response["sources"]]

        self.assertNotEqual(response["answer"], FALLBACK_AR)
        self.assertIn("غش", normalized_answer)
        self.assertTrue(any(term in normalized_answer for term in ("عقوب", "الماده الثامنه", "البند 7", "البند 15")))
        self.assertNotIn("انسحاب", normalized_answer)
        self.assertTrue(any("قواعد السلوك والانضباط الطلابي" in title for title in normalized_titles))

    def test_withdrawal_answer_stays_in_withdrawal_domain(self) -> None:
        response = answer_question("هل أستطيع الانسحاب من مقرر؟", top_k=4)
        normalized_answer = normalize_for_matching(response["answer"])
        normalized_titles = [normalize_for_matching(source.get("document_title", "")) for source in response["sources"]]
        normalized_articles = [normalize_for_matching(source.get("article", "")) for source in response["sources"]]

        self.assertNotEqual(response["answer"], FALLBACK_AR)
        self.assertIn("انسحاب", normalized_answer)
        self.assertTrue(any(term in normalized_answer for term in ("يجوز", "الماده السابعه عشره", "ثلاثه انسحابات")))
        self.assertNotIn("غش", normalized_answer)
        self.assertTrue(any("الدراسه والاختبارات" in title for title in normalized_titles))
        self.assertTrue(any("الماده السابعه عشره" in article for article in normalized_articles))


if __name__ == "__main__":
    unittest.main()