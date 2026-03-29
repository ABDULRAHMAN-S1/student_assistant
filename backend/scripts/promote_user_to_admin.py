from __future__ import annotations

import argparse
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


from app import database


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Promote an existing user to the admin role.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--user-id", dest="user_id")
    group.add_argument("--email")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    database.init_database()

    user = (
        database.fetch_user_by_id(args.user_id)
        if args.user_id
        else database.fetch_user_by_email((args.email or "").strip().lower())
    )
    if user is None:
        print("User not found.", file=sys.stderr)
        return 1

    updated_user = database.update_user_role(
        user_id=str(user["id"]),
        role=database.ADMIN_ROLE,
    )
    if updated_user is None:
        print("User not found.", file=sys.stderr)
        return 1

    print(
        "Promoted {email} ({user_id}) to admin.".format(
            email=updated_user["email"],
            user_id=updated_user["id"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())