from __future__ import annotations

import json
import sys
import time
import urllib.request
from typing import Any


BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
PASSWORD = "super-secure-password"


def post(path: str, payload: dict[str, Any], *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            **(headers or {}),
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def get(path: str, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(f"{BASE_URL}{path}", headers=headers or {})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> None:
    email = f"smoke.{int(time.time())}@example.com"
    register = post(
        "/auth/register",
        {
            "email": email,
            "password": PASSWORD,
            "full_name": "Smoke Test User",
        },
    )
    login = post(
        "/auth/login",
        {
            "email": email,
            "password": PASSWORD,
        },
    )

    headers = {"Authorization": f"Bearer {login['access_token']}"}
    health = get("/health", headers=headers)
    chat = post(
        "/chat",
        {
            "question": "هل أستطيع الانسحاب من مقرر؟",
            "top_k": 4,
        },
        headers=headers,
    )

    print(
        json.dumps(
            {
                "email": email,
                "registeredUserId": register["user"]["id"],
                "loginUserId": login["user"]["id"],
                "healthStatus": health["status"],
                "chatLanguage": chat["language"],
                "chatAnswer": chat["answer"],
                "sourceCount": len(chat["sources"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()