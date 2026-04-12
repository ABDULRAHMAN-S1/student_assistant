from typing import Any


try:
    from app.context_cleaning_utils import clean_context_lines
    from app.context_scoring_utils import score_line
    from app.question_analysis_utils import build_question_stems, list_like_question_kind
    from app.answer_item_parsing_utils import (
        anchored_block_indices,
        is_heading_like_line,
        is_rule_like_line,
        build_answer_item_text,
    )
    from app.status_code_utils import extract_status_code_terms
    from app.retrieve import normalize_for_matching
except ImportError:
    from context_cleaning_utils import clean_context_lines  # type: ignore
    from context_scoring_utils import score_line  # type: ignore
    from question_analysis_utils import build_question_stems, list_like_question_kind  # type: ignore
    from answer_item_parsing_utils import (  # type: ignore
        anchored_block_indices,
        is_heading_like_line,
        is_rule_like_line,
        build_answer_item_text,
    )
    from status_code_utils import extract_status_code_terms  # type: ignore
    from retrieve import normalize_for_matching  # type: ignore


def filter_items_for_question_kind(question: str, items: list[str]) -> list[str]:
    kind = list_like_question_kind(question)
    if kind is None:
        return items

    filtered: list[str] = []
    for item in items:
        normalized = normalize_for_matching(item)
        if not normalized:
            continue

        keep = True
        if "الصفحه" in normalized:
            keep = False
        elif kind == "conditions":
            keep = any(
                term in normalized
                for term in (
                    "الا ",
                    "ان يكون",
                    "عدم ",
                    "استكمال",
                    "حصول",
                    "انتظام",
                    "غير مرتبط",
                    "اجراءات",
                    "المستندات",
                )
            )
        elif kind == "penalties":
            keep = not normalized.endswith(":") and "العقوبات التبعية" not in normalized and any(
                term in normalized
                for term in (
                    "حرمان",
                    "راسب",
                    "الفصل من الجامعه",
                    "الفصل النهايي",
                    "تنبيه شفهي",
                    "تعهد كتابي",
                    "رفع المخالفه",
                )
            )
            if keep and False:  # penalty_question_domain not available here
                pass
        elif kind in {"rules", "policy"}:
            if any(
                term in normalized
                for term in (
                    "نموذج",
                    "اقر انا",
                    "توقيع",
                    "الحقول",
                    "الرقم الجامعي",
                )
            ):
                keep = False
            else:
                keep = any(
                    term in normalized
                    for term in (
                        "لا يحق",
                        "لا يجوز",
                        "يجوز",
                        "يلزم",
                        "يلتزم",
                        "تلتزم",
                        "اولوية",
                        "الحد الاعلي",
                        "منع",
                        "التنقل",
                        "التاكد",
                        "تخصيص",
                        "ضبط",
                        "النمط",
                        "المصدر",
                        "صلاحيات",
                        "شعب",
                        "حضور المقرر الحر",
                        "ارتداء",
                        "ملابس",
                        "اكسسوارات",
                        "رسومات",
                        "شعارات",
                        "الشورت",
                        "المظهر العام",
                        "الجهه المسووله",
                        "مسووليه",
                        "تتولي",
                        "تحال",
                        "لجنه التحقيق",
                        "لجنه",
                        "تاديب الطلاب",
                    )
                )
        elif kind == "system":
            keep = any(
                term in normalized
                for term in (
                    "النسبه المئويه",
                    "نقاط التقدير",
                    "الوزن",
                    "ممتاز",
                    "جيد",
                    "مقبول",
                    "راسب",
                    "dn",
                    "ic",
                    "np",
                    "ip",
                    "w",
                )
            )

        if keep:
            filtered.append(item)

    if filtered:
        return filtered
    if kind in {"penalties", "policy", "rules", "system"}:
        return []
    return items


def extract_context_answer_items(
    context: dict[str, Any],
    question: str,
    *,
    max_items: int = 3,
) -> list[str]:
    lines = clean_context_lines(context)
    if not lines:
        return []

    status_code_terms = extract_status_code_terms(question)
    if status_code_terms:
        matched_lines = []
        for line in lines:
            normalized_line = f" {normalize_for_matching(line)} "
            if any(f" {code} " in normalized_line for code in status_code_terms):
                matched_lines.append(build_answer_item_text(question, line))
        return _dedupe_preserve_order([line for line in matched_lines if line])[:max_items]

    question_stems = build_question_stems(question, "ar")
    normalized_question = normalize_for_matching(question)
    committee_referral_question = any(term in normalized_question for term in ("لجنه", "احال", "تحويل"))
    dress_rules_question = (
        list_like_question_kind(question) == "rules"
        and "ضوابط" in normalized_question
        and any(term in normalized_question for term in ("الزي", "مظهر"))
    )

    scored_lines: list[tuple[float, int, str]] = []
    for index, line in enumerate(lines):
        score = score_line(line, question_stems)
        normalized_line = normalize_for_matching(line)
        if committee_referral_question:
            if any(term in normalized_line for term in ("تحال", "لجنه التحقيق", "تاديب الطلاب")):
                score += 2.0
            if any(term in normalized_line for term in ("اتعهد", "المخالفه الثانيه", "اقر انا", "نموذج")):
                score -= 2.0
        if dress_rules_question:
            if any(term in normalized_line for term in ("ارتداء", "ملابس", "اكسسوارات", "رسومات", "شعارات", "الشورت")):
                score += 1.4
            if any(term in normalized_line for term in ("الرقم الجامعي", "عمل جولات", "رصد كل مخالفه", "الحقول", "نموذج", "توقيع")):
                score -= 1.4
        scored_lines.append((score, index, line))

    scored_lines.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    if not scored_lines:
        return []

    best_score, best_index, _ = scored_lines[0]
    list_like = list_like_question_kind(question) is not None
    block_indices = anchored_block_indices(lines, best_index)
    items: list[str] = []

    if list_like and block_indices:
        for index in block_indices:
            line = lines[index]
            if is_heading_like_line(line) or not is_rule_like_line(line):
                continue
            cleaned_item = build_answer_item_text(question, line)
            if cleaned_item:
                items.append(cleaned_item)
        items = filter_items_for_question_kind(question, _dedupe_preserve_order(items))
        if len(items) >= 2:
            return items[:max_items]

    fallback_items: list[str] = []
    for score, _, line in scored_lines:
        if score <= 0.0 and fallback_items:
            continue
        cleaned_item = build_answer_item_text(question, line)
        if not cleaned_item or is_heading_like_line(line):
            continue
        fallback_items.append(cleaned_item)
        if len(fallback_items) >= max_items:
            break

    fallback_items = filter_items_for_question_kind(question, _dedupe_preserve_order(fallback_items))
    if fallback_items:
        return fallback_items[:max_items]

    if best_score <= 0.0:
        return []
    if list_like_question_kind(question) in {"penalties", "policy", "rules", "system"}:
        return []
    best_item = build_answer_item_text(question, lines[best_index])
    return [best_item] if best_item else []


def extract_snippet(context: dict[str, Any], question: str, language: str) -> str:
    lines = clean_context_lines(context)
    if not lines:
        return ""

    if language != "ar":
        return _truncate_text(" ".join(lines[:3]), 320)

    extracted_items = extract_context_answer_items(context, question, max_items=3)
    if list_like_question_kind(question) is not None and len(extracted_items) >= 2:
        return "\n".join(f"- {item}" for item in extracted_items)
    if extracted_items:
        return " ".join(_dedupe_preserve_order(extracted_items[:2]))

    question_stems = build_question_stems(question, language)
    scored_lines = [(score_line(line, question_stems), line) for line in lines]
    scored_lines.sort(key=lambda item: item[0], reverse=True)

    chosen: list[str] = []
    for score, line in scored_lines:
        if score <= 0.0 and chosen:
            continue
        chosen.append(line)
        if len(chosen) == 2:
            break

    if not chosen:
        chosen = lines[:2]
    return " ".join(_dedupe_preserve_order(chosen))

try:
    from app.context_cleaning_utils import clean_context_lines
    from app.context_scoring_utils import score_line
    from app.question_analysis_utils import build_question_stems, list_like_question_kind
    from app.answer_item_parsing_utils import (
        anchored_block_indices,
        is_heading_like_line,
        is_rule_like_line,
        build_answer_item_text,
    )
    from app.status_code_utils import extract_status_code_terms
    from app.retrieve import normalize_for_matching
except ImportError:
    from context_cleaning_utils import clean_context_lines  # type: ignore
    from context_scoring_utils import score_line  # type: ignore
    from question_analysis_utils import build_question_stems, list_like_question_kind  # type: ignore
    from answer_item_parsing_utils import (  # type: ignore
        anchored_block_indices,
        is_heading_like_line,
        is_rule_like_line,
        build_answer_item_text,
    )
    from status_code_utils import extract_status_code_terms  # type: ignore
    from retrieve import normalize_for_matching  # type: ignore


def filter_items_for_question_kind(question: str, items: list[str]) -> list[str]:
    kind = list_like_question_kind(question)
    if kind is None:
        return items

    filtered: list[str] = []
    for item in items:
        normalized = normalize_for_matching(item)
        if not normalized:
            continue

        keep = True
        if "الصفحه" in normalized:
            keep = False
        elif kind == "conditions":
            keep = any(
                term in normalized
                for term in (
                    "الا ",
                    "ان يكون",
                    "عدم ",
                    "استكمال",
                    "حصول",
                    "انتظام",
                    "غير مرتبط",
                    "اجراءات",
                    "المستندات",
                )
            )
        elif kind == "penalties":
            keep = not normalized.endswith(":") and "العقوبات التبعية" not in normalized and any(
                term in normalized
                for term in (
                    "حرمان",
                    "راسب",
                    "الفصل من الجامعه",
                    "الفصل النهائي",
                    "تنبيه شفهي",
                    "تعهد كتابي",
                    "رفع المخالفه",
                )
            )
        if keep:
            filtered.append(item)
    return filtered


def extract_context_answer_items(
    context: dict[str, any],
    question: str,
    *,
    max_items: int = 3,
) -> list[str]:
    lines = clean_context_lines(context)
    if not lines:
        return []

    status_code_terms = extract_status_code_terms(question)
    if status_code_terms:
        matched_lines = []
        for line in lines:
            normalized_line = f" {normalize_for_matching(line)} "
            if any(f" {code} " in normalized_line for code in status_code_terms):
                matched_lines.append(build_answer_item_text(question, line))
        return _dedupe_preserve_order([line for line in matched_lines if line])[:max_items]

    question_stems = build_question_stems(question, "ar")
    normalized_question = normalize_for_matching(question)
    committee_referral_question = any(term in normalized_question for term in ("لجنه", "احال", "تحويل"))
    dress_rules_question = (
        list_like_question_kind(question) == "rules"
        and "ضوابط" in normalized_question
        and any(term in normalized_question for term in ("الزي", "مظهر"))
    )

    scored_lines: list[tuple[float, int, str]] = []
    for index, line in enumerate(lines):
        score = score_line(line, question_stems)
        normalized_line = normalize_for_matching(line)
        if committee_referral_question:
            if any(term in normalized_line for term in ("تحال", "لجنه التحقيق", "تاديب الطلاب")):
                score += 2.0
            if any(term in normalized_line for term in ("اتعهد", "المخالفه الثانيه", "اقر انا", "نموذج")):
                score -= 2.0
        if dress_rules_question:
            if any(term in normalized_line for term in ("ارتداء", "ملابس", "اكسسوارات", "رسومات", "شعارات", "الشورت")):
                score += 1.4
            if any(term in normalized_line for term in ("الرقم الجامعي", "عمل جولات", "رصد كل مخالفه", "الحقول", "نموذج", "توقيع")):
                score -= 1.4
        scored_lines.append((score, index, line))

    scored_lines.sort(key=lambda item: (item[0], -item[1]), reverse=True)
    if not scored_lines:
        return []

    best_score, best_index, _ = scored_lines[0]
    list_like = list_like_question_kind(question) is not None
    block_indices = anchored_block_indices(lines, best_index)
    items: list[str] = []

    if list_like and block_indices:
        for index in block_indices:
            line = lines[index]
            if is_heading_like_line(line) or not is_rule_like_line(line):
                continue
            cleaned_item = build_answer_item_text(question, line)
            if cleaned_item:
                items.append(cleaned_item)
        items = filter_items_for_question_kind(question, _dedupe_preserve_order(items))
        if len(items) >= 2:
            return items[:max_items]

    fallback_items: list[str] = []
    for score, _, line in scored_lines:
        if score <= 0.0 and fallback_items:
            continue
        cleaned_item = build_answer_item_text(question, line)
        if not cleaned_item or is_heading_like_line(line):
            continue
        fallback_items.append(cleaned_item)
        if len(fallback_items) >= max_items:
            break

    fallback_items = filter_items_for_question_kind(question, _dedupe_preserve_order(fallback_items))
    if fallback_items:
        return fallback_items[:max_items]

    if best_score <= 0.0:
        return []
    if list_like_question_kind(question) in {"penalties", "policy", "rules", "system"}:
        return []
    best_item = build_answer_item_text(question, lines[best_index])
    return [best_item] if best_item else []


def extract_snippet(context: dict[str, any], question: str, language: str) -> str:
    lines = clean_context_lines(context)
    if not lines:
        return ""

    if language != "ar":
        return _truncate_text(" ".join(lines[:3]), 320)

    extracted_items = extract_context_answer_items(context, question, max_items=3)
    if list_like_question_kind(question) is not None and len(extracted_items) >= 2:
        return "\n".join(f"- {item}" for item in extracted_items)
    if extracted_items:
        return " ".join(_dedupe_preserve_order(extracted_items[:2]))

    question_stems = build_question_stems(question, language)
    scored_lines = [(score_line(line, question_stems), line) for line in lines]
    scored_lines.sort(key=lambda item: item[0], reverse=True)

    chosen: list[str] = []
    for score, line in scored_lines:
        if score <= 0.0 and chosen:
            continue
        chosen.append(line)
        if len(chosen) == 2:
            break

    if not chosen:
        chosen = lines[:2]
    return " ".join(_dedupe_preserve_order(chosen))