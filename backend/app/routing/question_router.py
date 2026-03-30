from __future__ import annotations

from typing import Any

from app.retrieve import normalize_for_matching


class QuestionRouter:
    def __init__(self, *, fallback_service: Any | None = None) -> None:
        self.fallback_service = fallback_service

    def penalty_question_domain(self, question: str) -> str | None:
        normalized_question = normalize_for_matching(question)
        if "عقوب" not in normalized_question:
            return None
        if any(term in normalized_question for term in ("غش", "اختبار", "انتحال")):
            return "cheating"
        if any(term in normalized_question for term in ("غياب", "حضور", "حرمان", "محاضر")):
            return "attendance"
        if any(term in normalized_question for term in ("سكن", "اسكان", "اقام")):
            return "housing"
        if any(term in normalized_question for term in ("سلوك", "انضباط", "تاديب")):
            return "disciplinary"
        return "general"

    def is_gpa_formula_question(self, question: str) -> bool:
        normalized_question = normalize_for_matching(question)
        return "المعدل" in normalized_question and any(
            term in normalized_question for term in ("كيف", "يحسب", "يحتسب", "حساب", "احتساب")
        )

    def is_admission_conditions_question(self, question: str) -> bool:
        normalized_question = normalize_for_matching(question)
        if not any(term in normalized_question for term in ("شروط", "متطلبات")):
            return False
        if not any(term in normalized_question for term in ("قبول", "القبول", "ترشيح")):
            return False
        if any(term in normalized_question for term in ("سكن", "اسكان", "الاسكان", "السكن")):
            return False
        return True

    def is_withdrawal_question(self, question: str) -> bool:
        normalized_question = normalize_for_matching(question)
        return any(
            phrase in normalized_question
            for phrase in (
                "انسحاب",
                "انسحب",
                "هل اقدر انسحب",
                "اقدر انسحب",
                "هل اقدر احذف",
                "اقدر احذف",
                "حذف ماده",
                "حذف مقرر",
                "الانسحاب من ماده",
                "الانسحاب من مقرر",
            )
        )

    def is_missed_final_question(self, question: str) -> bool:
        normalized_question = normalize_for_matching(question)
        return (
            any(term in normalized_question for term in ("غاب", "غبت", "غياب", "يغيب", "فاتني"))
            and "اختبار" in normalized_question
            and any(term in normalized_question for term in ("نهائي", "النهايي", "النهائي"))
        )

    def is_attendance_limit_question(self, question: str) -> bool:
        normalized_question = normalize_for_matching(question)
        if self.is_missed_final_question(question):
            return False
        return any(term in normalized_question for term in ("غياب", "حضور", "حرمان")) and any(
            term in normalized_question for term in ("كم", "نسب", "حد", "اعلي", "اقصي", "ادني")
        )

    def detect_answer_mode(self, question: str, language: str) -> str:
        normalized_question = normalize_for_matching(question)
        lower_question = (question or "").lower()

        asks_upper_limit = bool(self.fallback_service and self.fallback_service.asks_upper_limit(normalized_question))
        asks_lower_limit = bool(self.fallback_service and self.fallback_service.asks_lower_limit(normalized_question))

        if self.is_gpa_formula_question(question):
            return "gpa_formula"
        if (
            asks_upper_limit
            or asks_lower_limit
            or "عدد الساعات" in normalized_question
            or "رقم محدد" in normalized_question
        ) and any(term in normalized_question for term in ("ساع", "عبء", "وحد")):
            return "load_limit"
        if "كم" in normalized_question and any(term in normalized_question for term in ("ساع", "عبء", "وحد", "مسموح")):
            return "load_limit"
        if "شروط" in normalized_question and any(term in normalized_question for term in ("سكن", "اسكان")):
            return "housing_conditions"
        if self.is_admission_conditions_question(question):
            return "admission_conditions"
        if "تصوير" in normalized_question and "محاضر" in normalized_question:
            return "lecture_recording"
        if "miss" in lower_question or self.is_missed_final_question(question):
            if "exam" in lower_question or "اختبار" in normalized_question:
                return "missed_final"
        if "withdraw" in lower_question or self.is_withdrawal_question(question):
            return "withdrawal"
        if "smok" in lower_question or "تدخين" in normalized_question:
            return "smoking"
        if self.penalty_question_domain(question) == "attendance":
            return "attendance_penalty"
        if ("penalty" in lower_question or "cheat" in lower_question) or (
            "غش" in normalized_question and "عقوب" in normalized_question
        ):
            return "penalty"
        return "general"

    def route_question(
        self,
        question: str,
        context: dict[str, Any] | None = None,
        *,
        language: str,
    ) -> dict[str, Any]:
        fallback_service = context.get("fallback_service") if context else self.fallback_service
        mode = self.detect_answer_mode(question, language) if language == "ar" else "general"
        fallback_mode = None
        if language == "ar" and fallback_service is not None:
            if mode != "general" and fallback_service.match_domain(mode, question):
                fallback_mode = mode
            elif fallback_service.detect_attendance(question):
                fallback_mode = "attendance"

        return {
            "mode": mode,
            "fallback_mode": fallback_mode,
            "uses_fallback_flow": bool(fallback_mode),
        }