from __future__ import annotations

from typing import Any

try:
    from app.retrieve import normalize_for_matching
except ImportError:
    from retrieve import normalize_for_matching  # type: ignore


def build_removable_metadata_lines(metadata: dict[str, Any]) -> set[str]:
    removable: set[str] = set()
    for value in (
        metadata.get("article", ""),
        metadata.get("document_title", ""),
        metadata.get("title", ""),
    ):
        normalized = normalize_for_matching(value)
        if normalized:
            removable.add(normalized)

    section = metadata.get("section", "")
    for part in section.split(">"):
        normalized = normalize_for_matching(part.strip())
        if normalized:
            removable.add(normalized)

    return removable


def clean_context_lines(context: dict[str, Any]) -> list[str]:
    metadata = context.get("metadata", {})
    removable = build_removable_metadata_lines(metadata)
    lines = []
    previous = ""
    for raw_line in context.get("content", "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        normalized = normalize_for_matching(line)
        if normalized in removable and normalized:
            continue
        if normalized == previous:
            continue
        previous = normalized
        lines.append(line)
    return lines