from __future__ import annotations

import re


ARABIC_DIGIT_TRANSLATION = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
NUMBER_PATTERN = re.compile(r"[\d٠-٩]+")


def normalize_reference_digits(text: str) -> str:
    return (text or "").translate(ARABIC_DIGIT_TRANSLATION)


def parse_reference_order(article: str, title: str) -> tuple[int, int | float]:
    combined = normalize_reference_digits(" ".join(part for part in (article, title) if part))

    for kind_rank, pattern in (
        (0, r"\bالمادة\s+(\d+)\b"),
        (1, r"\bالبند\s+(\d+)\b"),
        (2, r"\barticle\s+(\d+)\b"),
        (3, r"\bclause\s+(\d+)\b"),
    ):
        match = re.search(pattern, combined, flags=re.IGNORECASE)
        if match:
            return kind_rank, int(match.group(1))

    article_digits = NUMBER_PATTERN.findall(normalize_reference_digits(article))
    if article_digits:
        return 0, int(article_digits[0])

    title_digits = NUMBER_PATTERN.findall(normalize_reference_digits(title))
    if title_digits:
        return 1, int(title_digits[0])

    return 9, float("inf")
