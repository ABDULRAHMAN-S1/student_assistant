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
    return api_module, TestClient(api_module.app)


class EngagementNotificationsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory(prefix="engagement_notifications_")
        self.temp_path = Path(self._temp_dir.name)
        self.api_module, self.client = build_client(self.temp_path)

    def tearDown(self) -> None:
        self.client.close()
        self._temp_dir.cleanup()

    def _register(self, email: str, full_name: str) -> dict[str, object]:
        response = self.client.post(
            "/auth/register",
            json={
                "email": email,
                "password": "super-secure-password",
                "full_name": full_name,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _promote_to_admin(self, user_id: str) -> None:
        connection = sqlite3.connect(self.temp_path / "app.db")
        connection.execute(
            "UPDATE users SET role = ? WHERE id = ?",
            ("admin", user_id),
        )
        connection.commit()
        connection.close()

    @staticmethod
    def _headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"}

    def test_generation_is_separate_from_feed_read(self) -> None:
        student_session = self._register("student@example.com", "Student User")
        admin_session = self._register("admin@example.com", "Admin User")
        self._promote_to_admin(str(admin_session["user"]["id"]))

        admin_login = self.client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "super-secure-password"},
        )
        self.assertEqual(admin_login.status_code, 200)
        admin_headers = self._headers(admin_login.json()["access_token"])
        student_headers = self._headers(student_session["access_token"])

        update_profile_response = self.client.put(
            "/engagement/profile",
            headers=student_headers,
            json={
                "major": "computer science",
                "academic_level": "level 5",
                "track": "software engineering",
                "interests": ["ai", "internships"],
            },
        )
        self.assertEqual(update_profile_response.status_code, 200)
        self.assertEqual(
            update_profile_response.json()["profile"]["major"],
            "computer science",
        )

        create_content_response = self.client.post(
            "/engagement/content",
            headers=admin_headers,
            json={
                "content_type": "event",
                "title": "AI Career Event",
                "body": "Meet recruiters and prepare your CV.",
                "link_url": "https://example.edu/events/ai",
                "target_major": "computer science",
                "target_level": "level 5",
                "tags": ["AI", "career"],
                "priority": 7,
            },
        )
        self.assertEqual(create_content_response.status_code, 200)

        feed_response_before_generation = self.client.get(
            "/engagement/feed",
            headers=student_headers,
        )
        self.assertEqual(feed_response_before_generation.status_code, 200)
        self.assertEqual(
            feed_response_before_generation.json()["notifications"],
            [],
        )
        self.assertEqual(
            feed_response_before_generation.json()["unread_count"],
            0,
        )
        self.assertGreaterEqual(
            len(feed_response_before_generation.json()["suggestions"]),
            1,
        )

        generate_response = self.client.post(
            "/engagement/notifications/generate",
            headers=student_headers,
        )
        self.assertEqual(generate_response.status_code, 200)
        self.assertGreaterEqual(generate_response.json()["generated_count"], 1)

        feed_response = self.client.get("/engagement/feed", headers=student_headers)
        self.assertEqual(feed_response.status_code, 200)
        feed_payload = feed_response.json()
        self.assertGreaterEqual(feed_payload["unread_count"], 1)
        self.assertGreaterEqual(len(feed_payload["suggestions"]), 1)
        self.assertGreaterEqual(len(feed_payload["notifications"]), 1)

        first_notification = feed_payload["notifications"][0]
        self.assertEqual(first_notification["title"], "AI Career Event")
        self.assertIn("match_reasons", first_notification["metadata"])

        mark_read_response = self.client.patch(
            f"/engagement/notifications/{first_notification['id']}/read",
            headers=student_headers,
        )
        self.assertEqual(mark_read_response.status_code, 200)

        unread_only_feed = self.client.get("/engagement/feed", headers=student_headers)
        self.assertEqual(unread_only_feed.status_code, 200)
        self.assertEqual(unread_only_feed.json()["unread_count"], 0)
        self.assertEqual(unread_only_feed.json()["notifications"], [])

        include_read_feed = self.client.get(
            "/engagement/feed?include_read=true",
            headers=student_headers,
        )
        self.assertEqual(include_read_feed.status_code, 200)
        self.assertEqual(len(include_read_feed.json()["notifications"]), 1)
        self.assertTrue(include_read_feed.json()["notifications"][0]["is_read"])


if __name__ == "__main__":
    unittest.main()
