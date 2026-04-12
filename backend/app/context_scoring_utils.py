from __future__ import annotations

from typing import Any

try:
    from app.context_cleaning_utils import clean_context_lines
    from app.retrieve import light_stem, normalize_doc_type, normalize_for_matching, source_priority, tokenize_text
except ImportError:
    from context_cleaning_utils import clean_context_lines  # type: ignore
    from retrieve import light_stem, normalize_doc_type, normalize_for_matching, source_priority, tokenize_text  # type: ignore


def score_line(line: str, question_stems: list[str]) -> float:
    normalized_line = normalize_for_matching(line)
    line_stems = {light_stem(token) for token in tokenize_text(line)}
    overlap = sum(1 for stem in question_stems if stem in line_stems)
    score = float(overlap)

    if any(marker in normalized_line for marker in ("لا يسمح", "لا يجوز", "يجوز", "يسمح", "يحق")):
        score += 0.8
    if line.startswith(("المادة", "البند", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
        score += 0.2
    if "[غير واضح في المصدر]" in line:
        score -= 0.5
    return score


def context_answer_score(context: dict[str, Any], question_stems: list[str], language: str) -> float:
    base_score = float(context.get("score", 0.0))
    if language != "ar":
        return base_score

    metadata = context.get("metadata", {})
    doc_type = normalize_doc_type(metadata.get("doc_type", "regulation"))
    metadata_text = " ".join(
        value for value in (metadata.get("article", ""), metadata.get("section", ""), metadata.get("title", "")) if value
    )
    metadata_stems = {light_stem(token) for token in tokenize_text(metadata_text)}
    metadata_overlap = sum(1 for stem in question_stems if stem in metadata_stems)

    best_line_score = 0.0
    for line in clean_context_lines(context):
        best_line_score = max(best_line_score, score_line(line, question_stems))

    if metadata.get("status") == "partial":
        base_score -= 0.08

    return (base_score * 2.2) + best_line_score + (metadata_overlap * 0.9) + (0.15 * source_priority(doc_type))