from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
JSONL_PATH = PROCESSED_DIR / "taibah_regulations.jsonl"
MANIFEST_PATH = PROCESSED_DIR / "manifest.json"

MAX_CHUNK_CHARS = 900
TARGET_CHUNK_CHARS = 650
MIN_CHUNK_CHARS = 160
MAX_ITEMS_PER_CHUNK = 4
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
UNREADABLE_PLACEHOLDER = "[غير واضح في المصدر]"

CHAPTER_RE = re.compile(r"^(?:الباب|الفصل|القسم|الجزء)\s+.+$")
EXEC_RULE_RE = re.compile(r"^الق(?:اعدة|واعد)\s+التنفيذية(?:\s+ل.+)?[:：]?$")
ARTICLE_RE = re.compile(r"^المادة\s+.+?(?:[:：].*)?$")
SECTION_RE = re.compile(
    r"^(?:أولاً|أولا|ثانياً|ثانيا|ثالثاً|ثالثا|رابعاً|رابعا|خامساً|خامسا|سادساً|سادسا|"
    r"سابعاً|سابعا|ثامناً|ثامنا|تاسعاً|تاسعا|عاشراً|عاشرا|الحادي عشر|الثاني عشر)\s*[:：].*$"
)
ALPHA_HEADING_RE = re.compile(r"^[أ-ي]\.\s+.+$")
CLAUSE_RE = re.compile(r"^(?P<label>(?:\d+|[" + ARABIC_DIGITS + r"]+|[أ-ي]))[.)-]\s+.+$")
BULLET_RE = re.compile(r"^[-•]\s+.+$")


@dataclass
class ImproveStats:
    chunks_split: int = 0
    empty_sections_fixed: int = 0


@dataclass
class ContentBlock:
    kind: str
    lines: list[str]


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", (line or "").strip())


def canonical_line(line: str) -> str:
    normalized = normalize_line(line)
    normalized = re.sub(r"[^\w\u0600-\u06FF" + ARABIC_DIGITS + r"]+", "", normalized)
    return normalized.lower()


def strip_blank_edges(lines: list[str]) -> list[str]:
    trimmed = list(lines)
    while trimmed and not trimmed[0].strip():
        trimmed.pop(0)
    while trimmed and not trimmed[-1].strip():
        trimmed.pop()
    return trimmed


def is_list_item_start(line: str) -> bool:
    line = normalize_line(line)
    return bool(CLAUSE_RE.match(line) or BULLET_RE.match(line))


def is_short_colon_heading(line: str) -> bool:
    line = normalize_line(line)
    if not line or line.startswith("-") or line.startswith("["):
        return False
    if not (line.endswith(":") or line.endswith("：")):
        return False
    if len(line.split()) > 10:
        return False
    return True


def is_anchor_line(line: str) -> bool:
    line = normalize_line(line)
    if not line or line == UNREADABLE_PLACEHOLDER:
        return False
    return bool(
        CHAPTER_RE.match(line)
        or EXEC_RULE_RE.match(line)
        or ARTICLE_RE.match(line)
        or SECTION_RE.match(line)
        or ALPHA_HEADING_RE.match(line)
        or is_short_colon_heading(line)
        or line.startswith("الملحق")
    )


def parse_blocks(content: str) -> list[ContentBlock]:
    blocks: list[ContentBlock] = []
    current_kind = ""
    current_lines: list[str] = []

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if current_lines and current_lines[-1] != "":
                current_lines.append("")
            continue

        if is_anchor_line(line):
            if current_lines:
                blocks.append(ContentBlock(current_kind, strip_blank_edges(current_lines)))
            current_kind = "anchor"
            current_lines = [line]
            continue

        if is_list_item_start(line):
            if current_lines:
                blocks.append(ContentBlock(current_kind, strip_blank_edges(current_lines)))
            current_kind = "item"
            current_lines = [line]
            continue

        if not current_lines:
            current_kind = "text"
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        blocks.append(ContentBlock(current_kind, strip_blank_edges(current_lines)))

    return [block for block in blocks if block.lines]


def flatten_blocks(blocks: list[ContentBlock]) -> list[str]:
    lines: list[str] = []
    for block in blocks:
        lines.extend(block.lines)
    return lines


def dedupe_consecutive_lines(lines: list[str]) -> list[str]:
    deduped: list[str] = []
    for line in lines:
        if not deduped:
            deduped.append(line)
            continue
        if line == "" and deduped[-1] == "":
            continue
        if line and deduped[-1] and canonical_line(line) == canonical_line(deduped[-1]):
            continue
        deduped.append(line)
    return strip_blank_edges(deduped)


def build_context_lines(blocks: list[ContentBlock], max_chars: int = 260) -> list[str]:
    lines: list[str] = []
    total = 0
    for block in blocks:
        for line in block.lines:
            if not line:
                if lines and lines[-1] != "":
                    lines.append("")
                continue
            projected = total + len(line) + 1
            if lines and projected > max_chars:
                return strip_blank_edges(lines)
            lines.append(line)
            total = projected
    return strip_blank_edges(lines)


def combine_lines(prefix_lines: list[str], blocks: list[ContentBlock]) -> str:
    lines = list(prefix_lines)
    for line in flatten_blocks(blocks):
        if lines and line and canonical_line(lines[-1]) == canonical_line(line):
            continue
        if line == "" and lines and lines[-1] == "":
            continue
        lines.append(line)
    return "\n".join(dedupe_consecutive_lines(lines)).strip()


def build_entries_from_contents(entry: dict[str, Any], contents: list[str]) -> list[dict[str, Any]]:
    if len(contents) == 1:
        single = dict(entry)
        single["content"] = contents[0]
        return [single]

    updated_entries: list[dict[str, Any]] = []
    for index, content in enumerate(contents, start=1):
        improved = dict(entry)
        improved["chunk_id"] = f"{entry['chunk_id']}-{index:02d}"
        improved["content"] = content
        updated_entries.append(improved)
    return updated_entries


def split_lines_by_size(lines: list[str], prefix_lines: list[str]) -> list[str]:
    groups: list[list[str]] = []
    current: list[str] = []

    def current_size(candidate: list[str]) -> int:
        return len("\n".join(dedupe_consecutive_lines(prefix_lines + candidate)).strip())

    for line in lines:
        if not current:
            current = [line]
            continue
        if current_size(current + [line]) > TARGET_CHUNK_CHARS and current_size(current) >= MIN_CHUNK_CHARS:
            groups.append(current)
            current = [line]
        else:
            current.append(line)

    if current:
        groups.append(current)

    if len(groups) > 1 and current_size(groups[-1]) < MIN_CHUNK_CHARS:
        groups[-2].extend(groups[-1])
        groups.pop()

    return ["\n".join(dedupe_consecutive_lines(prefix_lines + group)).strip() for group in groups if group]


def split_list_entry(entry: dict[str, Any], blocks: list[ContentBlock]) -> list[str]:
    item_indices = [index for index, block in enumerate(blocks) if block.kind == "item"]
    if not item_indices:
        return [entry["content"]]

    first_item_index = item_indices[0]
    pre_blocks = blocks[:first_item_index]
    remaining_blocks = blocks[first_item_index:]

    if len(pre_blocks) >= 2 and pre_blocks[-1].kind == "anchor":
        reusable_context_lines = build_context_lines(pre_blocks[:-1])
        current_anchor_lines = list(pre_blocks[-1].lines)
        first_prefix_lines = flatten_blocks(pre_blocks)
    else:
        reusable_context_lines = build_context_lines(pre_blocks)
        current_anchor_lines = []
        first_prefix_lines = flatten_blocks(pre_blocks)

    outputs: list[str] = []
    group_blocks: list[ContentBlock] = []
    group_item_count = 0
    first_group = True

    def prefix_for_group() -> list[str]:
        if first_group:
            return first_prefix_lines
        return dedupe_consecutive_lines(reusable_context_lines + current_anchor_lines)

    def flush_group() -> None:
        nonlocal group_blocks, group_item_count, first_group
        if not group_blocks:
            return
        content = combine_lines(prefix_for_group(), group_blocks)
        outputs.append(content)
        group_blocks = []
        group_item_count = 0
        first_group = False

    for block in remaining_blocks:
        if block.kind == "anchor":
            flush_group()
            current_anchor_lines = list(block.lines)
            continue

        if block.kind == "text" and len("\n".join(block.lines)) > MAX_CHUNK_CHARS:
            flush_group()
            split_contents = split_lines_by_size(block.lines, prefix_for_group())
            outputs.extend(split_contents)
            first_group = False
            continue

        candidate_blocks = group_blocks + [block]
        candidate_content = combine_lines(prefix_for_group(), candidate_blocks)
        current_content = combine_lines(prefix_for_group(), group_blocks) if group_blocks else ""
        threshold_reached = (
            group_blocks
            and (
                group_item_count >= MAX_ITEMS_PER_CHUNK
                or (len(candidate_content) > TARGET_CHUNK_CHARS and len(current_content) >= MIN_CHUNK_CHARS)
            )
        )

        if threshold_reached:
            flush_group()
            group_blocks = [block]
            group_item_count = 1 if block.kind == "item" else 0
        else:
            group_blocks.append(block)
            if block.kind == "item":
                group_item_count += 1

    flush_group()

    if len(outputs) > 1 and len(outputs[-1]) < MIN_CHUNK_CHARS:
        outputs[-2] = "\n\n".join([outputs[-2], outputs[-1]]).strip()
        outputs.pop()

    return outputs or [entry["content"]]


def split_text_entry(entry: dict[str, Any], blocks: list[ContentBlock]) -> list[str]:
    if not blocks:
        return [entry["content"]]

    reusable_context_lines: list[str] = []
    first_prefix_lines: list[str] = []
    remaining_blocks = blocks

    if blocks[0].kind == "anchor":
        first_prefix_lines = list(blocks[0].lines)
        reusable_context_lines = build_context_lines([blocks[0]])
        remaining_blocks = blocks[1:]

    outputs: list[str] = []
    group_blocks: list[ContentBlock] = []
    first_group = True

    def prefix_for_group() -> list[str]:
        return first_prefix_lines if first_group else reusable_context_lines

    def flush_group() -> None:
        nonlocal group_blocks, first_group
        if not group_blocks:
            return
        outputs.append(combine_lines(prefix_for_group(), group_blocks))
        group_blocks = []
        first_group = False

    for block in remaining_blocks:
        if len("\n".join(block.lines)) > MAX_CHUNK_CHARS:
            flush_group()
            outputs.extend(split_lines_by_size(block.lines, prefix_for_group()))
            first_group = False
            continue

        candidate_blocks = group_blocks + [block]
        candidate_content = combine_lines(prefix_for_group(), candidate_blocks)
        current_content = combine_lines(prefix_for_group(), group_blocks) if group_blocks else ""
        if group_blocks and len(candidate_content) > TARGET_CHUNK_CHARS and len(current_content) >= MIN_CHUNK_CHARS:
            flush_group()
            group_blocks = [block]
        else:
            group_blocks.append(block)

    flush_group()

    if len(outputs) > 1 and len(outputs[-1]) < MIN_CHUNK_CHARS:
        outputs[-2] = "\n\n".join([outputs[-2], outputs[-1]]).strip()
        outputs.pop()

    return outputs or [entry["content"]]


def infer_section(entry: dict[str, Any]) -> str:
    section = (entry.get("section") or "").strip()
    if section:
        return section
    document_title = (entry.get("document_title") or "").strip()
    if document_title:
        return document_title
    article = (entry.get("article") or "").strip()
    if article:
        return article
    return section


def should_split_entry(entry: dict[str, Any], blocks: list[ContentBlock]) -> bool:
    content = entry.get("content", "")
    item_count = sum(1 for block in blocks if block.kind == "item")
    return bool(
        len(content) > MAX_CHUNK_CHARS
        or (item_count >= 8 and len(content) > 500)
        or (item_count >= 4 and len(content) > 700)
    )


def improve_entries(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], ImproveStats]:
    stats = ImproveStats()
    improved_entries: list[dict[str, Any]] = []

    for entry in entries:
        updated_entry = dict(entry)
        inferred_section = infer_section(updated_entry)
        if inferred_section != (updated_entry.get("section") or "").strip():
            updated_entry["section"] = inferred_section
            stats.empty_sections_fixed += 1

        blocks = parse_blocks(updated_entry["content"])
        split_contents = [updated_entry["content"]]

        if should_split_entry(updated_entry, blocks):
            item_count = sum(1 for block in blocks if block.kind == "item")
            split_contents = split_list_entry(updated_entry, blocks) if item_count else split_text_entry(updated_entry, blocks)

        new_entries = build_entries_from_contents(updated_entry, split_contents)
        if len(new_entries) > 1:
            stats.chunks_split += 1
        improved_entries.extend(new_entries)

    return improved_entries, stats


def load_entries() -> list[dict[str, Any]]:
    if not JSONL_PATH.exists():
        raise RuntimeError(f"Processed JSONL not found: {JSONL_PATH}")

    with JSONL_PATH.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def save_entries(entries: list[dict[str, Any]]) -> None:
    with JSONL_PATH.open("w", encoding="utf-8") as file:
        for entry in entries:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def update_manifest(entries: list[dict[str, Any]]) -> None:
    if not MANIFEST_PATH.exists():
        return

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    counts_by_source: dict[str, int] = defaultdict(int)
    partial_by_source: dict[str, bool] = defaultdict(bool)

    for entry in entries:
        source = entry["source_file"]
        counts_by_source[source] += 1
        if entry.get("status") == "partial":
            partial_by_source[source] = True

    for document in manifest.get("documents", []):
        source = document.get("source_file", "")
        if source in counts_by_source:
            document["number_of_chunks"] = counts_by_source[source]
            document["status"] = "partial" if partial_by_source[source] else "complete"

    manifest["chunk_count"] = len(entries)
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    configure_stdout()
    original_entries = load_entries()
    improved_entries, stats = improve_entries(original_entries)
    save_entries(improved_entries)
    update_manifest(improved_entries)

    print(
        json.dumps(
            {
                "original_chunk_count": len(original_entries),
                "improved_chunk_count": len(improved_entries),
                "chunks_split": stats.chunks_split,
                "empty_sections_fixed": stats.empty_sections_fixed,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
