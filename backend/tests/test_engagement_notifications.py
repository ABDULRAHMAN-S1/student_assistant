from __future__ import annotations

import importlib
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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

    def _login(self, email: str) -> dict[str, str]:
        response = self.client.post(
            "/auth/login",
            json={"email": email, "password": "super-secure-password"},
        )
        self.assertEqual(response.status_code, 200)
        return self._headers(response.json()["access_token"])

    def _create_content(
        self,
        *,
        headers: dict[str, str],
        title: str,
        body: str,
        priority: int,
        content_type: str = "event",
        link_url: str = "",
    ) -> None:
        response = self.client.post(
            "/engagement/content",
            headers=headers,
            json={
                "content_type": content_type,
                "title": title,
                "body": body,
                "link_url": link_url,
                "target_major": "computer science",
                "target_level": "level 5",
                "tags": ["AI", "career"],
                "priority": priority,
            },
        )
        self.assertEqual(response.status_code, 200)

    def _prepare_user_with_profile_and_admin(self) -> tuple[dict[str, str], dict[str, str]]:
        student_session = self._register("student@example.com", "Student User")
        admin_session = self._register("admin@example.com", "Admin User")
        self._promote_to_admin(str(admin_session["user"]["id"]))
        admin_headers = self._login("admin@example.com")
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
        return student_headers, admin_headers

    def test_generation_is_separate_from_feed_read(self) -> None:
        student_headers, admin_headers = self._prepare_user_with_profile_and_admin()
        self._create_content(
            headers=admin_headers,
            title="AI Career Event",
            body="Meet recruiters and prepare your CV.",
            priority=7,
            link_url="https://example.edu/events/ai",
        )

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

    def test_device_token_registration_and_deletion(self) -> None:
        session = self._register("student@example.com", "Student User")
        headers = self._headers(session["access_token"])

        register_response = self.client.post(
            "/engagement/device-tokens",
            headers=headers,
            json={
                "token": "fcm-token-1234567890abcdefghijklmnopqrstuvwxyz",
                "platform": "android",
                "device_name": "Pixel 9",
                "app_version": "1.2.3",
                "locale": "en",
            },
        )
        self.assertEqual(register_response.status_code, 200)
        token_payload = register_response.json()["token"]
        self.assertEqual(token_payload["platform"], "android")
        self.assertTrue(token_payload["is_active"])

        delete_response = self.client.delete(
            f"/engagement/device-tokens/{token_payload['id']}",
            headers=headers,
        )
        self.assertEqual(delete_response.status_code, 200)
        self.assertEqual(delete_response.json()["status"], "ok")

    def test_preferences_read_and_update(self) -> None:
        session = self._register("student@example.com", "Student User")
        headers = self._headers(session["access_token"])

        initial_response = self.client.get(
            "/engagement/notifications/preferences",
            headers=headers,
        )
        self.assertEqual(initial_response.status_code, 200)
        self.assertTrue(initial_response.json()["enable_push"])
        self.assertEqual(initial_response.json()["categories"], [])

        update_response = self.client.put(
            "/engagement/notifications/preferences",
            headers=headers,
            json={
                "enable_push": False,
                "categories": [
                    {
                        "category": "live_event",
                        "enable_push": False,
                        "enable_in_app": True,
                        "muted": True,
                    }
                ],
            },
        )
        self.assertEqual(update_response.status_code, 200)
        payload = update_response.json()
        self.assertFalse(payload["enable_push"])
        self.assertEqual(payload["categories"][0]["category"], "live_event")
        self.assertTrue(payload["categories"][0]["muted"])

    def test_feed_pagination_returns_cursor_metadata(self) -> None:
        student_headers, admin_headers = self._prepare_user_with_profile_and_admin()
        for index in range(3):
            self._create_content(
                headers=admin_headers,
                title=f"Priority Event {index}",
                body=f"Body {index}",
                priority=9 - index,
            )

        generate_response = self.client.post(
            "/engagement/notifications/generate?limit=10",
            headers=student_headers,
        )
        self.assertEqual(generate_response.status_code, 200)

        first_page = self.client.get(
            "/engagement/feed?include_read=true&limit=2",
            headers=student_headers,
        )
        self.assertEqual(first_page.status_code, 200)
        first_payload = first_page.json()
        self.assertEqual(len(first_payload["notifications"]), 2)
        self.assertTrue(first_payload["page"]["has_more"])
        self.assertTrue(first_payload["page"]["next_cursor"])

        second_page = self.client.get(
            f"/engagement/feed?include_read=true&limit=2&cursor={first_payload['page']['next_cursor']}",
            headers=student_headers,
        )
        self.assertEqual(second_page.status_code, 200)
        second_payload = second_page.json()
        self.assertGreaterEqual(len(second_payload["notifications"]), 1)
        self.assertNotEqual(
            first_payload["notifications"][0]["id"],
            second_payload["notifications"][0]["id"],
        )

    def test_mark_as_read_returns_notification_and_unread_count(self) -> None:
        student_headers, admin_headers = self._prepare_user_with_profile_and_admin()
        self._create_content(
            headers=admin_headers,
            title="Unread Event",
            body="Read state should update.",
            priority=6,
        )
        self.client.post("/engagement/notifications/generate", headers=student_headers)
        feed_response = self.client.get("/engagement/feed", headers=student_headers)
        notification_id = feed_response.json()["notifications"][0]["id"]

        mark_read_response = self.client.patch(
            f"/engagement/notifications/{notification_id}/read",
            headers=student_headers,
        )
        self.assertEqual(mark_read_response.status_code, 200)
        payload = mark_read_response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["notification"]["id"], notification_id)
        self.assertTrue(payload["notification"]["is_read"])
        self.assertEqual(payload["unread_count"], 0)

    def test_preference_enforcement_skips_push_delivery(self) -> None:
        student_headers, admin_headers = self._prepare_user_with_profile_and_admin()
        self._create_content(
            headers=admin_headers,
            title="Muted Event",
            body="Push should not send for this category.",
            priority=8,
        )
        self.client.put(
            "/engagement/notifications/preferences",
            headers=student_headers,
            json={
                "categories": [
                    {
                        "category": "live_event",
                        "enable_push": False,
                        "enable_in_app": True,
                        "muted": False,
                    }
                ]
            },
        )
        self.client.post(
            "/engagement/device-tokens",
            headers=student_headers,
            json={
                "token": "fcm-token-preference-abcdefghijklmnopqrstuvwxyz123456789",
                "platform": "android",
            },
        )

        with mock.patch("app.engagement_service.get_notification_delivery_service") as delivery_factory:
            mocked_service = mock.Mock()
            delivery_factory.return_value = mocked_service
            generate_response = self.client.post(
                "/engagement/notifications/generate",
                headers=student_headers,
            )
            self.assertEqual(generate_response.status_code, 200)
            mocked_service.send_notification.assert_not_called()

    def test_generated_notification_contains_route_contract(self) -> None:
        student_headers, admin_headers = self._prepare_user_with_profile_and_admin()
        self._create_content(
            headers=admin_headers,
            title="Linked Event",
            body="Route metadata should be present.",
            priority=9,
            link_url="https://example.edu/events/routed",
        )
        self.client.post("/engagement/notifications/generate", headers=student_headers)
        feed_response = self.client.get("/engagement/feed", headers=student_headers)
        self.assertEqual(feed_response.status_code, 200)
        notification = feed_response.json()["notifications"][0]
        route = notification["metadata"]["route"]
        self.assertEqual(route["type"], "external_url")
        self.assertEqual(route["payload"]["content_type"], "event")
        self.assertEqual(
            route["payload"]["url"],
            "https://example.edu/events/routed",
        )


if __name__ == "__main__":
    unittest.main()
