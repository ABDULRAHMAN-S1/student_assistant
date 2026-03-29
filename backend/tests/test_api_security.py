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
    api_module.answer_question = lambda question, top_k=4: {
        "question": question,
        "language": "ar",
        "answer": "إجابة اختبارية",
        "sources": [],
    }
    api_module.search = lambda query, top_k=5: [
        {
            "id": "record-1",
            "metadata": {
                "doc_type": "regulation",
                "document_title": "Policy",
                "section": "Section 1",
                "article": "Article 1",
                "title": "Title 1",
            },
            "score": 0.99,
            "content": "Matching content.",
        }
    ]
    return api_module, TestClient(api_module.app)


class ApiSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(prefix="student_assistant_backend_test_")
        self.temp_path = Path(self._temp_dir.name)
        self.api_module, self.client = build_client(self.temp_path)

    def tearDown(self) -> None:
        self.client.close()
        self._temp_dir.cleanup()

    def register_user(self) -> dict[str, str]:
        response = self.client.post(
            "/auth/register",
            json={
                "email": "student@example.com",
                "password": "super-secure-password",
                "full_name": "Student User",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        return {
            "access_token": payload["access_token"],
            "refresh_token": payload["refresh_token"],
        }

    def auth_headers(self, access_token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {access_token}"}

    def test_protected_routes_require_authentication(self) -> None:
        for route, body in (
            ("/health", None),
            ("/chat", {"question": "test"}),
            ("/search", {"query": "test"}),
            ("/feedback", {"question": "q", "answer": "a", "helpful": True, "language": "en", "sources": []}),
        ):
            if body is None:
                response = self.client.get(route)
            else:
                response = self.client.post(route, json=body)
            self.assertEqual(response.status_code, 401)

    def test_register_login_and_refresh_issue_tokens(self) -> None:
        register_response = self.client.post(
            "/auth/register",
            json={
                "email": "student@example.com",
                "password": "super-secure-password",
                "full_name": "Student User",
            },
        )
        self.assertEqual(register_response.status_code, 200)
        register_payload = register_response.json()
        self.assertTrue(register_payload["access_token"])
        self.assertTrue(register_payload["refresh_token"])
        self.assertLess(
            register_payload["access_expires_at"],
            register_payload["refresh_expires_at"],
        )

        login_response = self.client.post(
            "/auth/login",
            json={
                "email": "student@example.com",
                "password": "super-secure-password",
            },
        )
        self.assertEqual(login_response.status_code, 200)

        refresh_response = self.client.post(
            "/auth/refresh",
            json={"refresh_token": login_response.json()["refresh_token"]},
        )
        self.assertEqual(refresh_response.status_code, 200)
        self.assertTrue(refresh_response.json()["access_token"])

    def test_feedback_persists_only_hashed_content(self) -> None:
        tokens = self.register_user()

        response = self.client.post(
            "/feedback",
            headers=self.auth_headers(tokens["access_token"]),
            json={
                "question": "Sensitive question text",
                "answer": "Sensitive answer text",
                "helpful": True,
                "language": "en",
                "sources": [{"id": "src-1"}],
            },
        )
        self.assertEqual(response.status_code, 200)

        connection = sqlite3.connect(self.temp_path / "app.db")
        row = connection.execute(
            "SELECT question_hash, answer_hash, sources_json FROM feedback_events LIMIT 1"
        ).fetchone()
        connection.close()

        self.assertIsNotNone(row)
        self.assertNotEqual(row[0], "Sensitive question text")
        self.assertNotEqual(row[1], "Sensitive answer text")
        self.assertNotIn("Sensitive question text", row[2])

    def test_translation_is_disabled_without_explicit_configuration(self) -> None:
        tokens = self.register_user()
        response = self.client.post(
            "/translate",
            headers=self.auth_headers(tokens["access_token"]),
            json={"text": "مرحبا"},
        )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "translation_unavailable")


if __name__ == "__main__":
    unittest.main()