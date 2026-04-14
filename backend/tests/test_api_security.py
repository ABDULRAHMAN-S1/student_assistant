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
    os.environ["TRUST_FORWARDED_PROTO"] = "true"
    os.environ["TRUST_FORWARDED_FOR"] = "true"
    os.environ["TRUSTED_PROXY_IPS"] = ""
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

    def register_user(
        self,
        *,
        email: str = "student@example.com",
        full_name: str = "Student User",
    ) -> dict[str, str]:
        response = self.client.post(
            "/auth/register",
            json={
                "email": email,
                "password": "super-secure-password",
                "full_name": full_name,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        return {
            "user_id": payload["user"]["id"],
            "role": payload["user"]["role"],
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
        self.assertEqual(register_payload["user"]["role"], "student")
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
        self.assertEqual(login_response.json()["user"]["role"], "student")

        refresh_response = self.client.post(
            "/auth/refresh",
            json={"refresh_token": login_response.json()["refresh_token"]},
        )
        self.assertEqual(refresh_response.status_code, 200)
        self.assertTrue(refresh_response.json()["access_token"])
        self.assertEqual(refresh_response.json()["user"]["role"], "student")

    def test_me_returns_user_role_and_admin_route_requires_admin(self) -> None:
        tokens = self.register_user()

        me_response = self.client.get(
            "/me",
            headers=self.auth_headers(tokens["access_token"]),
        )
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["user"]["role"], "student")

        forbidden_response = self.client.get(
            "/admin",
            headers=self.auth_headers(tokens["access_token"]),
        )
        self.assertEqual(forbidden_response.status_code, 403)

        forbidden_users_response = self.client.get(
            "/users",
            headers=self.auth_headers(tokens["access_token"]),
        )
        self.assertEqual(forbidden_users_response.status_code, 403)

        forbidden_patch_response = self.client.patch(
            f"/users/{tokens['user_id']}/role",
            headers=self.auth_headers(tokens["access_token"]),
            json={"role": "admin"},
        )
        self.assertEqual(forbidden_patch_response.status_code, 403)

        connection = sqlite3.connect(self.temp_path / "app.db")
        connection.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            ("admin", tokens["user_id"]),
        )
        connection.commit()
        connection.close()

        login_response = self.client.post(
            "/auth/login",
            json={
                "email": "student@example.com",
                "password": "super-secure-password",
            },
        )
        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(login_response.json()["user"]["role"], "admin")

        second_user = self.register_user(
            email="learner@example.com",
            full_name="Learner User",
        )

        users_response = self.client.get(
            "/users",
            headers=self.auth_headers(login_response.json()["access_token"]),
        )
        self.assertEqual(users_response.status_code, 200)
        users_payload = users_response.json()["users"]
        self.assertEqual(len(users_payload), 2)
        user_roles = {user["email"]: user["role"] for user in users_payload}
        self.assertEqual(user_roles["student@example.com"], "admin")
        self.assertEqual(user_roles["learner@example.com"], "student")

        invalid_role_response = self.client.patch(
            f"/users/{second_user['user_id']}/role",
            headers=self.auth_headers(login_response.json()["access_token"]),
            json={"role": "owner"},
        )
        self.assertEqual(invalid_role_response.status_code, 422)

        patch_response = self.client.patch(
            f"/users/{second_user['user_id']}/role",
            headers=self.auth_headers(login_response.json()["access_token"]),
            json={"role": "admin"},
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.json()["user"]["role"], "admin")

        users_after_patch_response = self.client.get(
            "/users",
            headers=self.auth_headers(login_response.json()["access_token"]),
        )
        self.assertEqual(users_after_patch_response.status_code, 200)
        updated_roles = {
            user["email"]: user["role"]
            for user in users_after_patch_response.json()["users"]
        }
        self.assertEqual(updated_roles["learner@example.com"], "admin")

        admin_response = self.client.get(
            "/admin",
            headers=self.auth_headers(login_response.json()["access_token"]),
        )
        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(admin_response.json()["user"]["role"], "admin")

        second_login_response = self.client.post(
            "/auth/login",
            json={
                "email": "learner@example.com",
                "password": "super-secure-password",
            },
        )
        self.assertEqual(second_login_response.status_code, 200)
        self.assertEqual(second_login_response.json()["user"]["role"], "admin")

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

    def test_forwarded_headers_are_ignored_without_trusted_proxy_ips(self) -> None:
        tokens = self.register_user()
        # Even if forwarded headers are present, without TRUSTED_PROXY_IPS they must be ignored.
        response = self.client.get(
            "/health",
            headers={
                **self.auth_headers(tokens["access_token"]),
                "X-Forwarded-Proto": "https",
                "X-Forwarded-For": "203.0.113.10",
            },
        )
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()