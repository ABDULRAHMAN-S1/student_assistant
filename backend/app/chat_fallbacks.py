from __future__ import annotations

import re
from typing import Any

from app.record_index import iter_candidate_records
from app.reference_utils import normalize_reference_digits, parse_reference_order
from app.retrieve import light_stem, normalize_for_matching, tokenize_text


NUMBER_PATTERN = re.compile(r"[\d٠-٩]+")
ATTENDANCE_CONTEXT_TERMS = (
    "غياب",
    "حضور",
    "حرمان",
    "يحرم",
    "حرم",
    "محاضره",
    "محاضرات",
    "اختبار",
    "اختبارات",
)


class FallbackService:
    def asks_upper_limit(self, normalized_question: str) -> bool:
        return "حد" in normalized_question and any(term in normalized_question for term in ("اعلي", "اقصي"))

    def asks_lower_limit(self, normalized_question: str) -> bool:
        return "حد" in normalized_question and "ادني" in normalized_question

    def normalize_reference_digits(self, text: str) -> str:
        return normalize_reference_digits(text)

    def parse_reference_order(self, article: str, title: str) -> tuple[int, int | float]:
        return parse_reference_order(article, title)

    def context_search_text(self, context: dict[str, Any]) -> str:
        metadata = context.get("metadata", {})
        parts = [
            metadata.get("article", ""),
            metadata.get("section", ""),
            metadata.get("document_title", ""),
            context.get("content", ""),
        ]
        return normalize_for_matching(" ".join(part for part in parts if part))

    def detect_attendance(self, question: str) -> bool:
        return self.is_attendance_related_question(question)

    def is_attendance_related_question(self, question: str) -> bool:
        normalized_question = normalize_for_matching(question)
        if any(term in normalized_question for term in ("الاختبار النهايي", "الاختبار النهائي")) and any(
            term in normalized_question for term in ("غبت", "غاب", "فاتني", "يغيب", "غياب")
        ):
            return False
        if "تصوير" in normalized_question and "محاضر" in normalized_question:
            return False
        return any(
            term in normalized_question
            for term in (
                "غياب",
                "حضور",
                "حرمان",
                "يحرم",
                "حرم",
                "محاضره",
                "محاضرات",
                "نسبه الغياب",
                "نسبه الحضور",
            )
        )

    def attendance_query_terms(self, question: str) -> list[str]:
        normalized_question = normalize_for_matching(question)
        terms: list[str] = []
        seen: set[str] = set()

        for token in tokenize_text(question):
            stem = light_stem(token)
            if stem in ATTENDANCE_CONTEXT_TERMS and stem not in seen:
                seen.add(stem)
                terms.append(stem)

        for phrase, mapped_term in (
            ("نسبة الغياب", "غياب"),
            ("نسبه الغياب", "غياب"),
            ("نسبة الحضور", "حضور"),
            ("نسبه الحضور", "حضور"),
        ):
            if phrase in normalized_question and mapped_term not in seen:
                seen.add(mapped_term)
                terms.append(mapped_term)

        if any(term in normalized_question for term in ("غياب", "حضور", "حرمان")):
            for mapped_term in ("غياب", "حضور", "حرمان"):
                if mapped_term not in seen:
                    seen.add(mapped_term)
                    terms.append(mapped_term)

        return terms

    def context_attendance_match_count(self, context: dict[str, Any], question_terms: list[str]) -> int:
        if not question_terms:
            return 0

        searchable_text = " ".join(
            (
                self.context_search_text(context),
                normalize_for_matching(context.get("content", "")),
            )
        )
        return sum(1 for term in question_terms if term in searchable_text)

    def match_domain(self, mode: str, question: str) -> bool:
        normalized_question = normalize_for_matching(question)
        if mode == "attendance":
            return self.detect_attendance(question)
        if mode == "load_limit":
            return (
                self.asks_upper_limit(normalized_question)
                or self.asks_lower_limit(normalized_question)
                or ("عدد الساعات" in normalized_question)
                or ("رقم محدد" in normalized_question)
            ) and any(term in normalized_question for term in ("ساع", "عبء", "وحد", "مسموح"))
        if mode == "withdrawal":
            return any(term in normalized_question for term in ("انسحب", "انسحاب", "سحب", "حذف"))
        if mode == "missed_final":
            return any(term in normalized_question for term in ("غبت", "غاب", "فاتني", "يغيب", "غياب")) and any(
                term in normalized_question for term in ("نهائي", "النهايي", "النهائي", "اختبار")
            )
        if mode == "housing_conditions":
            return "شروط" in normalized_question and any(term in normalized_question for term in ("سكن", "اسكان"))
        if mode == "lecture_recording":
            return "تصوير" in normalized_question and "محاضر" in normalized_question
        if mode == "attendance_penalty":
            return self.detect_attendance(question)
        if mode == "penalty":
            return "غش" in normalized_question and "عقوب" in normalized_question
        if mode == "grading_system":
            return "تقدير" in normalized_question or "نقاط" in normalized_question or "نسبه" in normalized_question
        return False

    def get_fallback_context(
        self,
        mode: str,
        *,
        question: str = "",
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        if mode == "load_limit":
            return self.fallback_load_limit_contexts(question, limit=limit or 4)
        if mode == "housing_conditions":
            return self.fallback_housing_condition_contexts(limit=limit or 4)
        if mode == "attendance_limit":
            return self.fallback_attendance_limit_contexts(limit=limit or 4)
        if mode == "withdrawal":
            return self.fallback_withdrawal_contexts(limit=limit or 4)
        if mode == "missed_final":
            return self.fallback_missed_final_contexts(limit=limit or 4)
        if mode == "lecture_recording":
            return self.fallback_lecture_recording_contexts(limit=limit or 2)
        if mode == "penalty":
            return self.fallback_cheating_penalty_contexts(limit=limit or 4)
        if mode == "grading_system":
            return self.fallback_grading_system_contexts(limit=limit or 6)
        return []

    def _build_context(self, record: dict[str, Any], score: float) -> dict[str, Any]:
        return {
            "id": record["id"],
            "content": record["content"],
            "metadata": record["metadata"],
            "score": score,
        }

    def fallback_load_limit_contexts(self, question: str, limit: int = 4) -> list[dict[str, Any]]:
        normalized_question = normalize_for_matching(question)
        asks_upper = self.asks_upper_limit(normalized_question)
        asks_lower = self.asks_lower_limit(normalized_question)

        candidates: list[tuple[float, dict[str, Any]]] = []
        for record in iter_candidate_records(
            (
                "العبء الدراسي",
                "الحد الاعلى",
                "الحد الادنى",
                "الوحدات الدراسية",
                "التسجيل",
            )
        ):
            haystack = " ".join((record.get("normalized_metadata", ""), record.get("normalized_content", ""))).strip()
            metadata_text = record.get("normalized_metadata", "")

            if not any(
                term in haystack
                for term in (
                    "العبء الدراسي",
                    "الحد الاعلي للعبء الدراسي",
                    "الحد الادني للعبء الدراسي",
                    "الوحدات الدراسيه",
                    "يسمح للطالب التسجيل",
                    "اقل من الحد الادني للعبء الدراسي",
                )
            ):
                continue

            score = 0.0
            if "لايحه الدراسه والاختبارات" in metadata_text:
                score += 2.0
            if "العبء الدراسي" in haystack:
                score += 3.0
            if "الوحدات الدراسيه" in haystack:
                score += 1.5
            if "يسمح للطالب التسجيل" in haystack:
                score += 1.5
            if "محدده من مجلس الجامعه" in haystack:
                score += 1.0
            if "سكن" in metadata_text or "اسكان" in metadata_text:
                score -= 6.0

            if asks_upper:
                if "الحد الاعلي للعبء الدراسي" in haystack:
                    score += 5.0
                else:
                    score -= 1.0
            elif asks_lower:
                if "الحد الادني للعبء الدراسي" in haystack:
                    score += 5.0
                if "اقل من الحد الادني للعبء الدراسي" in haystack:
                    score += 2.0
            else:
                if "الحد الاعلي للعبء الدراسي" in haystack or "الحد الادني للعبء الدراسي" in haystack:
                    score += 2.5

            if score <= 0:
                continue

            candidates.append((score, self._build_context(record, score)))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [context for _, context in candidates[:limit]]

    def fallback_housing_condition_contexts(self, limit: int = 4) -> list[dict[str, Any]]:
        candidates: list[tuple[float, dict[str, Any]]] = []
        for record in iter_candidate_records(("الاسكان الطلابي", "شروط القبول", "القواعد المنظمة")):
            metadata_text = record.get("normalized_metadata", "")
            if "القواعد المنظمه للاسكان الطلابي" not in metadata_text:
                continue
            if "شروط القبول بالاسكان الطلابي" not in metadata_text:
                continue

            score = 2.0
            article_text = normalize_for_matching(record.get("metadata", {}).get("article", ""))
            if "البند" in article_text:
                score += 1.5
            if any(term in record.get("normalized_content", "") for term in ("غير مرتبطين", "استكمال", "انتظامهم", "المستندات")):
                score += 1.0

            candidates.append((score, self._build_context(record, score)))

        candidates.sort(
            key=lambda item: self.parse_reference_order(
                item[1]["metadata"].get("article", ""),
                item[1]["metadata"].get("title", ""),
            )
        )
        return [context for _, context in candidates[:limit]]

    def fallback_attendance_limit_contexts(self, limit: int = 4) -> list[dict[str, Any]]:
        candidates: list[tuple[float, dict[str, Any]]] = []
        for record in iter_candidate_records(("نسبة الحضور", "حضور", "حرمان", "الدراسة والاختبارات")):
            haystack = " ".join((record.get("normalized_metadata", ""), record.get("normalized_content", ""))).strip()
            if not any(term in haystack for term in ("نسبه الحضور", "حضور", "حرمان")):
                continue
            if "لايحه الدراسه والاختبارات" not in haystack:
                continue

            score = 1.0
            if "نسبه الحضور" in haystack:
                score += 2.0
            if "حرمان" in haystack:
                score += 1.5
            if "البند 1" in haystack:
                score += 1.2

            candidates.append((score, self._build_context(record, score)))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [context for _, context in candidates[:limit]]

    def fallback_withdrawal_contexts(self, limit: int = 4) -> list[dict[str, Any]]:
        candidates: list[tuple[float, dict[str, Any]]] = []
        for record in iter_candidate_records(("انسحاب", "المادة السابعة عشرة", "طلب الانسحاب")):
            haystack = " ".join((record.get("normalized_metadata", ""), record.get("normalized_content", ""))).strip()
            if "انسحاب" not in haystack:
                continue
            if "لايحه الدراسه والاختبارات" not in haystack:
                continue

            score = 1.0
            if "الماده السابعه عشره" in haystack:
                score += 2.4
            if "يجوز للطالب الانسحاب من مقرر دراسي" in haystack:
                score += 2.0
            if "طلب الانسحاب" in haystack:
                score += 1.2
            if "لا يسمح" in haystack:
                score += 0.8

            candidates.append((score, self._build_context(record, score)))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [context for _, context in candidates[:limit]]

    def fallback_missed_final_contexts(self, limit: int = 4) -> list[dict[str, Any]]:
        candidates: list[tuple[float, dict[str, Any]]] = []
        for record in iter_candidate_records(("الاختبار النهائي", "اختبار بديل", "أداء الاختبار النهائي لعذر")):
            haystack = " ".join((record.get("normalized_metadata", ""), record.get("normalized_content", ""))).strip()
            if "لايحه الدراسه والاختبارات" not in haystack:
                continue
            if not any(
                term in haystack
                for term in (
                    "الاختبار النهايي",
                    "الطالب الغايب عن الاختبار النهايي",
                    "اداء الاختبار النهايي لعذر",
                    "اختبار بديل",
                    "الماده الحاديه والثلاثون",
                    "الماده الثانيه والثلاثون",
                )
            ):
                continue

            score = 1.0
            if "الماده الحاديه والثلاثون" in haystack:
                score += 2.8
            if "الماده الثانيه والثلاثون" in haystack:
                score += 2.4
            if "الطالب الغايب عن الاختبار النهايي" in haystack:
                score += 2.0
            if "اداء الاختبار النهايي لعذر" in haystack:
                score += 1.6
            if "صفرا" in haystack or "صفر" in haystack:
                score += 1.8
            if "اختبار بديل" in haystack:
                score += 1.4

            candidates.append((score, self._build_context(record, score)))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [context for _, context in candidates[:limit]]

    def fallback_lecture_recording_contexts(self, limit: int = 2) -> list[dict[str, Any]]:
        candidates: list[tuple[float, dict[str, Any]]] = []
        for record in iter_candidate_records(("تصوير المحاضرات", "تسجيل", "موافقة المحاضر")):
            haystack = " ".join((record.get("normalized_metadata", ""), record.get("normalized_content", ""))).strip()
            if not all(term in haystack for term in ("تصوير", "محاضر")):
                continue
            if "موافقه" not in haystack and "تسجيل" not in haystack:
                continue

            score = 1.0
            if "المخالفات الطلابيه" in haystack:
                score += 1.2
            if "قبل اخذ موافقه المحاضر الخطيه" in haystack:
                score += 2.0

            candidates.append((score, self._build_context(record, score)))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [context for _, context in candidates[:limit]]

    def fallback_cheating_penalty_contexts(self, limit: int = 4) -> list[dict[str, Any]]:
        candidates: list[tuple[float, dict[str, Any]]] = []
        for record in iter_candidate_records(("قواعد السلوك والانضباط الطلابي", "الاختبار النهائي", "راسب")):
            haystack = " ".join((record.get("normalized_metadata", ""), record.get("normalized_content", ""))).strip()
            if "قواعد السلوك والانضباط الطلابي" not in haystack:
                continue
            if "الماده الثامنه" not in haystack:
                continue
            if not any(
                term in haystack
                for term in (
                    "الاختبار الدوري",
                    "الاختبار النصفي",
                    "الاختبار النهايي",
                    "راسب",
                    "المقرر",
                    "الفصل من الجامعه",
                    "الفصل النهايي من الجامعه",
                )
            ):
                continue
            if any(term in haystack for term in ("سكن", "اسكان", "الاسكان")) and "غش" not in haystack:
                continue

            score = 1.0
            if "الاختبار النهايي" in haystack:
                score += 1.8
            if "راسب" in haystack and "المقرر" in haystack:
                score += 1.5
            if "الفصل النهايي من الجامعه" in haystack:
                score += 1.5
            if "الاختبار الدوري" in haystack or "الاختبار النصفي" in haystack:
                score += 1.2

            candidates.append((score, self._build_context(record, score)))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [context for _, context in candidates[:limit]]

    def fallback_grading_system_contexts(self, limit: int = 6) -> list[dict[str, Any]]:
        candidates: list[tuple[float, dict[str, Any]]] = []
        for record in iter_candidate_records(("التقديرات", "نقاط التقدير", "النسبة المئوية")):
            haystack = " ".join((record.get("normalized_metadata", ""), record.get("normalized_content", ""))).strip()
            if "التقديرات" not in haystack:
                continue
            if "لايحه الدراسه والاختبارات" not in haystack:
                continue

            score = 1.0
            if "النسبه المئويه" in haystack or "نقاط التقدير" in haystack or "الوزن" in haystack:
                score += 2.0
            if any(term in haystack for term in ("95 100", "90 الي اقل من 95", "85 الي اقل من 90", "ممتاز", "جيد جدا", "مقبول", "راسب")):
                score += 1.5
            if "الفصل التاسع التقديرات" in haystack:
                score += 1.0

            candidates.append((score, self._build_context(record, score)))

        candidates.sort(key=lambda item: item[0], reverse=True)
        return [context for _, context in candidates[:limit]]