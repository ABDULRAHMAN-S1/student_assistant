from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.chat import answer_question
from app.retrieve import normalize_for_matching


class HousingConditionsIntentTests(unittest.TestCase):
    def test_housing_conditions_returns_admission_conditions_not_visiting_or_penalties(self) -> None:
        resp = answer_question("ما شروط السكن الجامعي؟", top_k=4)
        self.assertEqual(resp.get("route_mode"), "housing_conditions")

        answer = normalize_for_matching(resp.get("answer", ""))
        # Must not drift to "visiting study" rules.
        self.assertNotIn("الزياره", answer)
        self.assertNotIn("نظام الزياره", answer)
        # Must not include deprivation/denial/punishment wording for housing conditions.
        self.assertNotIn("حرمان", answer)
        self.assertNotIn("عقوب", answer)
        # Must not include operational entry/exit rules like housing cards.
        self.assertNotIn("بطاقه السكن", answer)

        sources = resp.get("sources", []) or []
        haystack = normalize_for_matching(
            " ".join(
                str(s.get("source", "")) + " " + str(s.get("document_title", "")) + " " + str(s.get("title", ""))
                for s in sources
            )
        )
        self.assertIn("اسكان", haystack)


if __name__ == "__main__":
    unittest.main()

