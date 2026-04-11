"""End-to-end tests for the enhanced feedback feature."""
from __future__ import annotations

import importlib
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def build_client(tmp_path: Path) -> tuple[object, TestClient]:
    os.environ["APP_ENV"] = "test"
    os.environ["JWT_SECRET"] = "test-secret"
    os.environ["APP_DB_PATH"] = str(tmp_path / "app.db")
    os.environ["ENABLE_TRANSLATION"] = "false"
    os.environ["REQUIRE_HTTPS"] = "false"
    os.environ["CORS_ORIGINS"] = "http://localhost:3000"

    from app.config import get_settings
    get_settings.cache_clear()

    import app.api as api_module
    api_module = importlib.reload(api_module)

    # Mock answer_question to return route_mode
    api_module.answer_question = lambda question, top_k=4: {
        "question": question,
        "language": "ar",
        "answer": "إجابة اختبارية",
        "sources": [{"id": "src-1", "doc_type": "regulation", "title": "Test"}],
        "route_mode": "withdrawal",
    }
    return api_module, TestClient(api_module.app)


class FeedbackE2ETests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(prefix="feedback_e2e_")
        self.temp_path = Path(self._temp_dir.name)
        self.api_module, self.client = build_client(self.temp_path)

    def tearDown(self) -> None:
        self.client.close()
        self._temp_dir.cleanup()

    def _register_and_auth(self) -> dict[str, str]:
        resp = self.client.post("/auth/register", json={
            "email": "tester@example.com",
            "password": "super-secure-password",
            "full_name": "Tester",
        })
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        return {"Authorization": f"Bearer {payload['access_token']}"}

    def _db_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.temp_path / "app.db")
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------------
    # Test 1: /chat returns route_mode
    # ------------------------------------------------------------------
    def test_chat_response_includes_route_mode(self) -> None:
        headers = self._register_and_auth()
        resp = self.client.post("/chat", headers=headers, json={"question": "سؤال"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("route_mode", data)
        self.assertEqual(data["route_mode"], "withdrawal")

    # ------------------------------------------------------------------
    # Test 2: helpful=true feedback works
    # ------------------------------------------------------------------
    def test_helpful_true_stores_metadata_only(self) -> None:
        headers = self._register_and_auth()
        resp = self.client.post("/feedback", headers=headers, json={
            "question": "Sensitive question here",
            "answer": "Sensitive answer here",
            "helpful": True,
            "language": "en",
            "sources": [{"id": "src-1"}],
            "reason": "",
            "route_mode": "general",
        })
        self.assertEqual(resp.status_code, 200)

        conn = self._db_conn()
        row = conn.execute(
            "SELECT question_hash, answer_hash, question_text, answer_text, reason, route_mode, helpful FROM feedback_events LIMIT 1"
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        # helpful=true → question_text and answer_text must be empty (privacy)
        self.assertEqual(row["question_text"], "")
        self.assertEqual(row["answer_text"], "")
        # hashes should be populated
        self.assertTrue(len(row["question_hash"]) > 0)
        self.assertTrue(len(row["answer_hash"]) > 0)
        # plaintext must NOT appear in hashes
        self.assertNotEqual(row["question_hash"], "Sensitive question here")
        self.assertNotEqual(row["answer_hash"], "Sensitive answer here")
        # route_mode should be stored
        self.assertEqual(row["route_mode"], "general")
        # reason should be empty
        self.assertEqual(row["reason"], "")
        self.assertEqual(row["helpful"], 1)

    # ------------------------------------------------------------------
    # Test 3: helpful=false stores question_text, answer_text,  and reason
    # ------------------------------------------------------------------
    def test_helpful_false_stores_full_text_and_reason(self) -> None:
        headers = self._register_and_auth()
        resp = self.client.post("/feedback", headers=headers, json={
            "question": "ما هي شروط الانسحاب؟",
            "answer": "يمكنك الانسحاب قبل نهاية الأسبوع الثامن.",
            "helpful": False,
            "language": "ar",
            "sources": [{"id": "src-2"}],
            "reason": "الإجابة غير دقيقة",
            "route_mode": "withdrawal",
        })
        self.assertEqual(resp.status_code, 200)

        conn = self._db_conn()
        row = conn.execute(
            "SELECT question_text, answer_text, reason, route_mode, helpful FROM feedback_events ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row["helpful"], 0)
        # helpful=false → plaintext MUST be stored
        self.assertEqual(row["question_text"], "ما هي شروط الانسحاب؟")
        self.assertEqual(row["answer_text"], "يمكنك الانسحاب قبل نهاية الأسبوع الثامن.")
        self.assertEqual(row["reason"], "الإجابة غير دقيقة")
        self.assertEqual(row["route_mode"], "withdrawal")

    # ------------------------------------------------------------------
    # Test 4: helpful=false without reason (user skipped)
    # ------------------------------------------------------------------
    def test_helpful_false_without_reason(self) -> None:
        headers = self._register_and_auth()
        resp = self.client.post("/feedback", headers=headers, json={
            "question": "سؤال عام",
            "answer": "إجابة عامة",
            "helpful": False,
            "language": "ar",
            "sources": [],
            "reason": "",
            "route_mode": "general",
        })
        self.assertEqual(resp.status_code, 200)

        conn = self._db_conn()
        row = conn.execute(
            "SELECT question_text, answer_text, reason FROM feedback_events ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()

        self.assertEqual(row["question_text"], "سؤال عام")
        self.assertEqual(row["answer_text"], "إجابة عامة")
        self.assertEqual(row["reason"], "")

    # ------------------------------------------------------------------
    # Test 5: backward compat — reason and route_mode are optional
    # ------------------------------------------------------------------
    def test_feedback_without_new_fields_still_works(self) -> None:
        headers = self._register_and_auth()
        # Old client sends without reason/route_mode
        resp = self.client.post("/feedback", headers=headers, json={
            "question": "backward compat question",
            "answer": "backward compat answer",
            "helpful": True,
            "language": "en",
            "sources": [],
        })
        self.assertEqual(resp.status_code, 200)

        conn = self._db_conn()
        row = conn.execute(
            "SELECT reason, route_mode FROM feedback_events ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        conn.close()

        self.assertEqual(row["reason"], "")
        self.assertEqual(row["route_mode"], "")

    # ------------------------------------------------------------------
    # Test 6: migration adds columns to existing table
    # ------------------------------------------------------------------
    def test_migration_adds_new_columns(self) -> None:
        conn = self._db_conn()
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(feedback_events)").fetchall()}
        conn.close()

        self.assertIn("reason", columns)
        self.assertIn("route_mode", columns)
        self.assertIn("question_text", columns)
        self.assertIn("answer_text", columns)

    # ------------------------------------------------------------------
    # Test 7: reason max length validation
    # ------------------------------------------------------------------
    def test_reason_max_length_rejected(self) -> None:
        headers = self._register_and_auth()
        resp = self.client.post("/feedback", headers=headers, json={
            "question": "q",
            "answer": "a",
            "helpful": False,
            "language": "ar",
            "sources": [],
            "reason": "x" * 101,
            "route_mode": "general",
        })
        self.assertEqual(resp.status_code, 422)

    # ------------------------------------------------------------------
    # Test 8: no public endpoint exposes feedback data
    # ------------------------------------------------------------------
    def test_no_public_feedback_read_endpoint(self) -> None:
        headers = self._register_and_auth()
        resp = self.client.get("/feedback", headers=headers)
        self.assertIn(resp.status_code, (404, 405))


if __name__ == "__main__":
    unittest.main()
