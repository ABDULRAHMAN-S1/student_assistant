from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from typing import Any, Iterable

try:
    from app.retrieve import get_chunk_records, normalize_for_matching, tokenize_text
except ImportError:
    from retrieve import get_chunk_records, normalize_for_matching, tokenize_text  # type: ignore


@lru_cache(maxsize=1)
def _build_index() -> tuple[list[dict[str, Any]], dict[str, set[int]]]:
    records = get_chunk_records()
    token_index: dict[str, set[int]] = defaultdict(set)

    for index, record in enumerate(records):
        searchable_parts = [
            record.get("normalized_metadata", ""),
            record.get("normalized_content", ""),
        ]
        searchable_text = " ".join(part for part in searchable_parts if part).strip()
        if not searchable_text:
            continue

        normalized_tokens = set(tokenize_text(searchable_text))
        for token in normalized_tokens:
            token_index[token].add(index)

    return records, token_index


def iter_candidate_records(seed_terms: Iterable[str]) -> list[dict[str, Any]]:
    records, token_index = _build_index()
    candidate_ids: set[int] = set()

    for seed_term in seed_terms:
        normalized_seed = normalize_for_matching(seed_term)
        if not normalized_seed:
            continue
        for token in tokenize_text(normalized_seed):
            candidate_ids.update(token_index.get(token, set()))

    if not candidate_ids:
        return records

    return [records[index] for index in sorted(candidate_ids)]