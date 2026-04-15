from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
VECTORDB_DIR = DATA_DIR / "vectordb"
OUTPUT_JSONL_PATH = PROCESSED_DIR / "taibah_regulations.jsonl"
CHUNKS_PATH = OUTPUT_JSONL_PATH
MANIFEST_PATH = PROCESSED_DIR / "manifest.json"
SUPPORTED_EXTENSIONS = {".txt"}
MIN_CHUNK_WORDS = 200
TARGET_CHUNK_WORDS = 320
MAX_CHUNK_WORDS = 500

METADATA_KEYS = {
    "اسم الملف",
    "العنوان",
    "النوع",
    "المصدر",
    "اللغة",
}
UNREADABLE_PLACEHOLDER = "[غير واضح في المصدر]"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"

PAGE_NUMBER_RE = re.compile(r"^(?:صفحة\s*)?\d+(?:\s*/\s*\d+)?$")
SEPARATOR_RE = re.compile(r"^[-_=*~•·]{3,}$")
UNREADABLE_RE = re.compile(
    r"(?:غير\s*واضح|غير\s*مقروء|متضرر\s*جزئي|النص\s*الأصلي.*متضرر|غير\s*واضح\s*في\s*المصدر)"
)
CHAPTER_RE = re.compile(r"^(?:الباب|الفصل|القسم|الجزء)\s+.+$")
EXEC_RULE_RE = re.compile(r"^الق(?:اعدة|واعد)\s+التنفيذية(?:\s+ل.+)?[:：]?$")
ARTICLE_RE = re.compile(r"^المادة\s+.+?(?:[:：].*)?$")
SECTION_RE = re.compile(
    r"^(?:أولاً|أولا|ثانياً|ثانيا|ثالثاً|ثالثا|رابعاً|رابعا|خامساً|خامسا|سادساً|سادسا|"
    r"سابعاً|سابعا|ثامناً|ثامنا|تاسعاً|تاسعا|عاشراً|عاشرا|الحادي عشر|الثاني عشر)\s*[:：].*$"
)
ENGLISH_SECTION_RE = re.compile(
    r"^(?:first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\s*:\s+.+$",
    re.IGNORECASE,
)
CLAUSE_RE = re.compile(r"^(?P<label>(?:\d+|[" + ARABIC_DIGITS + r"]+|[أ-ي]))[.)-]\s+.+$")
DEFINITION_RE = re.compile(r"^(?P<label>[^:]{2,70}):\s+.+$")
FAQ_QUESTION_RE = re.compile(r"^(?:س(?:ؤال)?|q(?:uestion)?)\s*[:：\-]\s*.+$", re.IGNORECASE)
MARKDOWN_HEADER_RE = re.compile(r"^\s{0,3}#{1,6}\s*")
MARKDOWN_BULLET_RE = re.compile(r"^\s*[*-]\s+")
TABLE_ALIGNMENT_CELL_RE = re.compile(r"^:?-{3,}:?$")
HTML_BREAK_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


@dataclass
class ProcessingStats:
    metadata_removed: int = 0
    page_noise_removed: int = 0
    repeated_headers_removed: int = 0
    duplicate_lines_removed: int = 0
    unreadable_lines_normalized: int = 0


@dataclass
class ChunkQaSummary:
    heading_only_removed: int = 0
    duplicate_chunks_removed: int = 0
    tiny_chunks_flagged: int = 0
    partial_chunks_flagged: int = 0
    missing_metadata_flagged: int = 0


@dataclass
class DocumentContext:
    chapter: str = ""
    section: str = ""
    article: str = ""


def ensure_directories() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    VECTORDB_DIR.mkdir(parents=True, exist_ok=True)


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def normalize_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = text.replace("\u200f", "").replace("\u200e", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("–", "-").replace("—", "-")
    text = HTML_BREAK_RE.sub("؛ ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[ ]*([،؛:؟!])\s*", r"\1 ", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\]", "]", text)
    text = re.sub(r"\[\s+", "[", text)
    text = re.sub(r"\s+/", "/", text)
    text = re.sub(r"/\s+", "/", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_line(line: str) -> str:
    return normalize_text(line).replace("\n", " ")


def clean_markdown_line(line: str) -> str:
    cleaned = line.replace("**", "").replace("__", "")
    cleaned = MARKDOWN_HEADER_RE.sub("", cleaned)
    cleaned = cleaned.replace("`", "")
    return cleaned.strip()


def is_markdown_table_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or "|" not in stripped:
        return False
    return len([part for part in stripped.split("|") if part.strip()]) >= 2


def split_table_cells(line: str) -> list[str]:
    stripped = line.strip().strip("|")
    return [clean_markdown_line(part.strip()) for part in stripped.split("|")]


def is_table_alignment_row(cells: list[str]) -> bool:
    meaningful = [cell for cell in cells if cell]
    if not meaningful:
        return False
    return all(TABLE_ALIGNMENT_CELL_RE.match(cell) for cell in meaningful)


def format_table_value(header: str, value: str) -> str:
    cleaned_header = clean_markdown_line(header)
    cleaned_value = clean_markdown_line(value)
    if not cleaned_value:
        return ""

    range_match = re.match(r"^(?P<start>[^-]+?)\s*-\s*(?P<end>.+)$", cleaned_value)
    if range_match and any(keyword in cleaned_header for keyword in ("النسبة", "المعدل", "الدرجة")):
        return f"{cleaned_header}: من {range_match.group('start').strip()} إلى {range_match.group('end').strip()}"

    if cleaned_header:
        return f"{cleaned_header}: {cleaned_value}"
    return cleaned_value


def convert_table_row(header_cells: list[str], row_cells: list[str]) -> str:
    if not row_cells:
        return ""

    subject = row_cells[0].strip()
    if not subject:
        return ""

    descriptor = ""
    value_parts: list[str] = []

    for index, value in enumerate(row_cells[1:], start=1):
        if not value:
            continue
        header = header_cells[index] if index < len(header_cells) else ""
        if index == 1 and any(keyword in header for keyword in ("التقدير", "المعنى")):
            descriptor = clean_markdown_line(value)
            continue
        formatted = format_table_value(header, value)
        if formatted:
            value_parts.append(formatted)

    prefix = f"{subject} ({descriptor})" if descriptor else subject
    if not value_parts:
        return prefix
    return f"{prefix}: {'، '.join(value_parts)}"


def convert_markdown_table(table_lines: list[str]) -> list[str]:
    rows = [split_table_cells(line) for line in table_lines]
    rows = [row for row in rows if any(cell for cell in row)]
    if not rows:
        return []

    header_cells = rows[0]
    data_rows = rows[1:]
    if data_rows and is_table_alignment_row(data_rows[0]):
        data_rows = data_rows[1:]
    if not data_rows:
        return [clean_markdown_line(" ".join(cell for cell in header_cells if cell))]

    converted_rows = [convert_table_row(header_cells, row) for row in data_rows]
    return [row for row in converted_rows if row]


def preprocess_raw_text(raw_text: str) -> str:
    normalized_text = raw_text.replace("\ufeff", "").replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized_text.splitlines()
    processed_lines: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        if is_markdown_table_line(line):
            table_lines: list[str] = []
            while index < len(lines) and is_markdown_table_line(lines[index]):
                table_lines.append(lines[index])
                index += 1
            processed_lines.extend(convert_markdown_table(table_lines))
            continue

        processed_lines.append(clean_markdown_line(line))
        index += 1

    return "\n".join(processed_lines)


def canonical_line(line: str) -> str:
    normalized = normalize_line(line)
    normalized = re.sub(r"[^\w\u0600-\u06FF" + ARABIC_DIGITS + r"]+", "", normalized)
    return normalized.lower()


def count_words(text: str) -> int:
    return len([part for part in (text or "").split() if part.strip()])


def normalize_language_hint(value: str) -> str:
    normalized = normalize_text(value).lower()
    if not normalized:
        return ""

    if any(token in normalized for token in ("english", "الانجليزي", "الإنجليزي", "الانجليزية", "الإنجليزية", "انجليزي")):
        return "en"
    if any(token in normalized for token in ("arabic", "بالعربي", "العربي", "العربية", "عربي")):
        return "ar"
    if re.search(r"(?<![a-z])en(?![a-z])", normalized):
        return "en"
    if re.search(r"(?<![a-z])ar(?![a-z])", normalized):
        return "ar"
    return ""


def detect_document_language(
    metadata: dict[str, str],
    source_file: str,
    document_title: str,
    content: str,
) -> str:
    for candidate in (metadata.get("اللغة", ""), source_file, document_title):
        detected = normalize_language_hint(candidate)
        if detected:
            return detected

    arabic_chars = len(re.findall(r"[\u0600-\u06FF]", content))
    latin_chars = len(re.findall(r"[A-Za-z]", content))
    return "en" if latin_chars > arabic_chars else "ar"


def detect_doc_type(filename: str, document_title: str = "", content: str = "") -> str:
    lowered_filename = filename.lower()
    lowered_title = document_title.lower()
    lowered_content = content.lower()
    explicit_identity = " ".join(part for part in (lowered_filename, lowered_title) if part).strip()
    # Priority by explicit filename markers
    if "لائحة" in lowered_filename or "لائح" in lowered_filename:
        return "regulation"
    if "سياسة" in lowered_filename or "ضوابط" in lowered_filename:
        return "policy"
    if "دليل" in explicit_identity and "لائح" not in explicit_identity and "سياس" not in explicit_identity and "ضوابط" not in explicit_identity:
        return "guide"
    if "أسئلة" in explicit_identity or "faq" in explicit_identity or "سؤال" in explicit_identity:
        return "faq"
    # Fallback from content signals
    if "لائحة" in lowered_content or "لوائح" in lowered_content:
        return "regulation"
    if "سياسة" in lowered_content or "ضوابط" in lowered_content:
        return "policy"
    if "دليل" in lowered_content:
        return "guide"
    if "أسئلة" in lowered_content or "faq" in lowered_content or "سؤال" in lowered_content:
        return "faq"
    # English fallback
    if "guide" in explicit_identity and "regulation" not in explicit_identity and "policy" not in explicit_identity:
        return "guide"
    if "policy" in lowered_filename:
        return "policy"
    if "faq" in lowered_filename:
        return "faq"
    if "regulation" in lowered_filename or "rule" in lowered_filename:
        return "regulation"
    return "guide"


def is_title_like(line: str, title: str) -> bool:
    canonical_title = canonical_line(title)
    canonical_candidate = canonical_line(line)
    if not canonical_title or not canonical_candidate:
        return False
    return canonical_title in canonical_candidate or canonical_candidate in canonical_title


def parse_metadata_line(line: str) -> tuple[str, str] | None:
    match = re.match(r"^([^:：]+):\s*(.+)$", line)
    if not match:
        return None
    key = match.group(1).strip()
    if key not in METADATA_KEYS:
        return None
    return key, match.group(2).strip()


def extract_front_matter(lines: list[str]) -> tuple[dict[str, str], list[str]]:
    metadata: dict[str, str] = {}
    content_start = 0

    for index, raw_line in enumerate(lines):
        line = normalize_line(raw_line)
        if not line:
            continue

        parsed = parse_metadata_line(line)
        if parsed and index <= 12:
            key, value = parsed
            metadata[key] = value
            content_start = index + 1
            continue

        break

    return metadata, lines[content_start:]


def detect_title(metadata: dict[str, str], content_lines: list[str], source_file: str) -> tuple[str, str]:
    if metadata.get("العنوان"):
        return metadata["العنوان"], "metadata"

    for raw_line in content_lines:
        line = normalize_line(raw_line)
        if line and not is_noise_line(line):
            return line, "content"

    return Path(source_file).stem, "filename"


def is_noise_line(line: str) -> bool:
    if not line:
        return True
    if PAGE_NUMBER_RE.match(line) or SEPARATOR_RE.match(line):
        return True
    return False


def is_unreadable_line(line: str) -> bool:
    if not line:
        return False
    if line == UNREADABLE_PLACEHOLDER:
        return True
    if UNREADABLE_RE.search(line):
        return True
    if "�" in line:
        return True
    readable_char_count = len(re.findall(r"[A-Za-z\u0600-\u06FF0-9" + ARABIC_DIGITS + r"]", line))
    suspicious_count = len(re.findall(r"[^A-Za-z\u0600-\u06FF0-9" + ARABIC_DIGITS + r"\s\[\]\(\)\-_/.:،؛؟!]", line))
    return readable_char_count == 0 and suspicious_count >= 4


def detect_repeated_header_candidates(lines: list[str], title: str) -> set[str]:
    normalized_lines = [normalize_line(line) for line in lines if normalize_line(line)]
    counts = Counter(normalized_lines)
    candidates: set[str] = set()

    for line, count in counts.items():
        if count < 2 or len(line) > 120:
            continue
        if line == title:
            candidates.add(line)
            continue
        if "جامعة طيبة" in line and any(keyword in line for keyword in ("لائحة", "قواعد", "ضوابط")):
            candidates.add(line)

    return candidates


def clean_lines(lines: list[str], title: str) -> tuple[list[str], ProcessingStats]:
    stats = ProcessingStats()
    repeated_headers = detect_repeated_header_candidates(lines, title)
    repeated_header_counts: Counter[str] = Counter()
    cleaned_lines: list[str] = []

    for raw_line in lines:
        line = normalize_line(raw_line)
        if not line:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue

        if parse_metadata_line(line):
            stats.metadata_removed += 1
            continue

        if is_noise_line(line):
            stats.page_noise_removed += 1
            continue

        if line in repeated_headers:
            repeated_header_counts[line] += 1
            if repeated_header_counts[line] > 1:
                stats.repeated_headers_removed += 1
                continue

        if is_unreadable_line(line):
            line = UNREADABLE_PLACEHOLDER
            stats.unreadable_lines_normalized += 1

        if cleaned_lines:
            previous_nonempty = next((item for item in reversed(cleaned_lines) if item), "")
            if previous_nonempty and canonical_line(previous_nonempty) == canonical_line(line):
                stats.duplicate_lines_removed += 1
                continue

        cleaned_lines.append(line)

    while cleaned_lines and cleaned_lines[0] == "":
        cleaned_lines.pop(0)
    while cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()

    return cleaned_lines, stats


def next_nonempty_line(lines: list[str], start_index: int) -> str:
    for line in lines[start_index:]:
        if line:
            return line
    return ""


def is_standalone_heading(line: str, next_line: str) -> bool:
    if not line or len(line) > 90 or line == UNREADABLE_PLACEHOLDER:
        return False
    if any(
        (
            CHAPTER_RE.match(line),
            EXEC_RULE_RE.match(line),
            ARTICLE_RE.match(line),
            SECTION_RE.match(line),
            ENGLISH_SECTION_RE.match(line),
            CLAUSE_RE.match(line),
        )
    ):
        return False
    if ":" in line or "：" in line or line.startswith("-") or line.startswith("["):
        return False
    if line.endswith((".", "؟", "!", "،", "؛")):
        return False
    word_count = len(line.split())
    if word_count == 0 or word_count > 8:
        return False
    return bool(next_line and next_line != UNREADABLE_PLACEHOLDER)


def is_colon_heading(line: str, next_line: str) -> bool:
    if not line or line == UNREADABLE_PLACEHOLDER:
        return False
    if any((CHAPTER_RE.match(line), EXEC_RULE_RE.match(line), ARTICLE_RE.match(line), SECTION_RE.match(line))):
        return False
    if not (line.endswith(":") or line.endswith("：")):
        return False
    if line.startswith("-") or line.startswith("["):
        return False
    word_count = len(line.rstrip(":：").split())
    if word_count == 0 or word_count > 8:
        return False
    return bool(next_line and (next_line.startswith("-") or CLAUSE_RE.match(next_line) or next_line == UNREADABLE_PLACEHOLDER))


def is_heading_like_line(line: str) -> bool:
    normalized = normalize_line(line)
    if not normalized or normalized == UNREADABLE_PLACEHOLDER:
        return False
    if any(
        (
            CHAPTER_RE.match(normalized),
            EXEC_RULE_RE.match(normalized),
            ARTICLE_RE.match(normalized),
            SECTION_RE.match(normalized),
            ENGLISH_SECTION_RE.match(normalized),
        )
    ):
        return True
    if normalized.endswith((":", "：")) and len(normalized.split()) <= 10:
        return True
    return False


def is_faq_question_line(line: str, next_line: str) -> bool:
    if not line or line == UNREADABLE_PLACEHOLDER:
        return False
    if FAQ_QUESTION_RE.match(line):
        return True
    if line.endswith(("؟", "?")):
        return bool(next_line and next_line != UNREADABLE_PLACEHOLDER)
    return False


def compose_section(context: DocumentContext) -> str:
    parts = [context.chapter, context.section]
    return " > ".join(part for part in parts if part)


def build_prefix(context: DocumentContext, include_article_line: str | None = None) -> list[str]:
    prefix: list[str] = []
    if context.chapter:
        prefix.append(context.chapter)
    if context.section and context.section != context.chapter:
        prefix.append(context.section)
    if include_article_line:
        prefix.append(include_article_line)

    deduped: list[str] = []
    for item in prefix:
        if not deduped or canonical_line(deduped[-1]) != canonical_line(item):
            deduped.append(item)
    return deduped


def collapse_chunk_lines(lines: list[str]) -> list[str]:
    collapsed: list[str] = []
    for line in lines:
        if not line:
            if collapsed and collapsed[-1] != "":
                collapsed.append("")
            continue
        if not collapsed or canonical_line(collapsed[-1]) != canonical_line(line):
            collapsed.append(line)

    while collapsed and collapsed[0] == "":
        collapsed.pop(0)
    while collapsed and collapsed[-1] == "":
        collapsed.pop()
    return collapsed


def extract_definition_label(line: str) -> str:
    match = DEFINITION_RE.match(line)
    return match.group("label").strip() if match else ""


def extract_clause_label(line: str) -> str:
    match = CLAUSE_RE.match(line)
    if not match:
        return ""
    label = match.group("label").strip()
    return label.translate(str.maketrans(ARABIC_DIGITS, "0123456789"))


def build_entries(
    source_file: str,
    document_title: str,
    doc_type: str,
    language: str,
    lines: list[str],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    context = DocumentContext()
    current_lines: list[str] = []
    current_section = ""
    current_article = ""

    def flush() -> None:
        nonlocal current_lines, current_section, current_article
        collapsed = collapse_chunk_lines(current_lines)
        if not collapsed:
            current_lines = []
            current_section = compose_section(context)
            current_article = context.article
            return

        content = "\n".join(collapsed).strip()
        if not content:
            current_lines = []
            current_section = compose_section(context)
            current_article = context.article
            return

        status = "partial" if UNREADABLE_PLACEHOLDER in content else "complete"
        entry_document_title = document_title
        if doc_type == "faq" and current_article:
            entry_document_title = current_article
        entries.append(
            {
                "source_file": source_file,
                "document_title": entry_document_title,
                "doc_type": doc_type,
                "language": language,
                "section": current_section,
                "article": current_article,
                "content": content,
                "status": status,
            }
        )
        current_lines = []
        current_section = compose_section(context)
        current_article = context.article

    def start_chunk(prefix: list[str], article_value: str = "") -> None:
        nonlocal current_lines, current_section, current_article
        current_section = compose_section(context)
        current_article = article_value
        current_lines = prefix.copy()

    def is_chapter_heading(line: str) -> bool:
        if not CHAPTER_RE.match(line):
            return False
        if doc_type != "regulation" and ":" in line and not line.rstrip().endswith((":", "ï¼š")):
            return False
        return True

    for index, line in enumerate(lines):
        if not line:
            if current_lines and current_lines[-1] != "":
                current_lines.append("")
            continue

        next_line = next_nonempty_line(lines, index + 1)

        if is_chapter_heading(line):
            flush()
            context.chapter = line
            context.section = ""
            context.article = ""
            continue

        if EXEC_RULE_RE.match(line):
            flush()
            context.section = line.rstrip(":：")
            context.article = ""
            continue

        if not context.article and (
            SECTION_RE.match(line)
            or ENGLISH_SECTION_RE.match(line)
            or is_standalone_heading(line, next_line)
            or is_colon_heading(line, next_line)
        ):
            flush()
            context.section = line.rstrip(":：")
            context.article = ""
            continue

        if ARTICLE_RE.match(line):
            flush()
            context.article = line.rstrip()
            start_chunk(build_prefix(context, context.article), article_value=context.article)
            continue

        if doc_type == "faq" and is_faq_question_line(line, next_line):
            flush()
            context.article = line.rstrip()
            start_chunk(build_prefix(context, context.article), article_value=context.article)
            continue

        if doc_type == "regulation" and not context.article and context.section and CLAUSE_RE.match(line):
            flush()
            clause_label = extract_clause_label(line)
            start_chunk(
                build_prefix(context) + [line],
                article_value=f"البند {clause_label}" if clause_label else "",
            )
            continue

        if doc_type == "regulation" and not context.article and DEFINITION_RE.match(line) and not CLAUSE_RE.match(line):
            flush()
            definition_label = extract_definition_label(line)
            start_chunk(build_prefix(context) + [line], article_value=definition_label)
            continue

        if not current_lines:
            current_article = context.article
            current_section = compose_section(context)
            current_lines = build_prefix(context, context.article if context.article else None)

        if not current_lines or canonical_line(current_lines[-1]) != canonical_line(line):
            current_lines.append(line)

    flush()
    return entries


def build_prefix_lines(entry: dict[str, Any]) -> list[str]:
    prefix: list[str] = []
    for part in str(entry.get("section", "")).split(" > "):
        cleaned = normalize_line(part)
        if cleaned and (not prefix or canonical_line(prefix[-1]) != canonical_line(cleaned)):
            prefix.append(cleaned)

    article = normalize_line(str(entry.get("article", "")))
    if article and (not prefix or canonical_line(prefix[-1]) != canonical_line(article)):
        prefix.append(article)
    return prefix


def strip_prefix_lines(content_lines: list[str], prefix_lines: list[str]) -> list[str]:
    remaining = content_lines[:]
    prefix_index = 0

    while remaining and prefix_index < len(prefix_lines):
        current = remaining[0]
        if not current:
            remaining.pop(0)
            continue
        if canonical_line(current) == canonical_line(prefix_lines[prefix_index]):
            remaining.pop(0)
            prefix_index += 1
            continue
        break

    return remaining


def normalize_chunk_content(content: str) -> str:
    return canonical_line(content.replace("\n", " "))


def extract_body_lines(entry: dict[str, Any]) -> list[str]:
    prefix_lines = build_prefix_lines(entry)
    content_lines = [normalize_line(line) for line in str(entry.get("content", "")).splitlines()]
    body_lines = strip_prefix_lines(content_lines, prefix_lines)
    return [line for line in body_lines if line]


def collect_chunk_qa_flags(entry: dict[str, Any]) -> list[str]:
    body_lines = extract_body_lines(entry)
    substantive_lines = [line for line in body_lines if line != UNREADABLE_PLACEHOLDER]
    body_text = "\n".join(substantive_lines).strip()
    body_word_count = count_words(body_text)

    flags: list[str] = []
    if entry.get("status") == "partial":
        flags.append("partial_chunk")
    if not str(entry.get("document_title", "")).strip():
        flags.append("missing_title")
    if not str(entry.get("section", "")).strip() and not str(entry.get("article", "")).strip():
        flags.append("missing_locator")
    if not substantive_lines or all(is_heading_like_line(line) for line in substantive_lines):
        flags.append("heading_only")
    elif body_word_count and body_word_count < 12:
        flags.append("tiny_chunk")

    deduped_flags: list[str] = []
    for flag in flags:
        if flag not in deduped_flags:
            deduped_flags.append(flag)
    return deduped_flags


def apply_chunk_qa(source_file: str, entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], ChunkQaSummary]:
    summary = ChunkQaSummary()
    filtered_entries: list[dict[str, Any]] = []
    seen_contents: set[str] = set()

    for entry in entries:
        qa_flags = collect_chunk_qa_flags(entry)
        normalized_content = normalize_chunk_content(str(entry.get("content", "")))

        if normalized_content and normalized_content in seen_contents:
            summary.duplicate_chunks_removed += 1
            continue
        if "heading_only" in qa_flags:
            summary.heading_only_removed += 1
            continue

        if normalized_content:
            seen_contents.add(normalized_content)

        if "tiny_chunk" in qa_flags:
            summary.tiny_chunks_flagged += 1
        if "partial_chunk" in qa_flags:
            summary.partial_chunks_flagged += 1
        if "missing_title" in qa_flags or "missing_locator" in qa_flags:
            summary.missing_metadata_flagged += 1

        improved_entry = dict(entry)
        if qa_flags:
            improved_entry["qa_flags"] = qa_flags
        filtered_entries.append(improved_entry)

    return assign_chunk_ids(source_file, filtered_entries), summary


def split_large_block(block_text: str) -> list[str]:
    block_text = block_text.strip()
    if not block_text:
        return []
    if count_words(block_text) <= MAX_CHUNK_WORDS:
        return [block_text]

    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[\.\!\؟\؛])\s+", block_text)
        if sentence.strip()
    ]
    if len(sentences) <= 1:
        return [block_text]

    parts: list[str] = []
    current: list[str] = []
    current_words = 0

    for sentence in sentences:
        sentence_words = count_words(sentence)
        if current and current_words >= MIN_CHUNK_WORDS and current_words + sentence_words > MAX_CHUNK_WORDS:
            parts.append(" ".join(current).strip())
            current = [sentence]
            current_words = sentence_words
            continue

        current.append(sentence)
        current_words += sentence_words

    if current:
        parts.append(" ".join(current).strip())

    return [part for part in parts if part]


def build_semantic_blocks(body_lines: list[str]) -> list[str]:
    blocks: list[str] = []
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_lines
        text = "\n".join(line for line in current_lines if line).strip()
        if text:
            if count_words(text) > MAX_CHUNK_WORDS:
                blocks.extend(split_large_block(text))
            else:
                blocks.append(text)
        current_lines = []

    for line in body_lines:
        if not line:
            flush()
            continue

        if current_lines and any(
            (
                CHAPTER_RE.match(line),
                EXEC_RULE_RE.match(line),
                ARTICLE_RE.match(line),
                SECTION_RE.match(line),
                ENGLISH_SECTION_RE.match(line),
                CLAUSE_RE.match(line),
            )
        ):
            flush()

        current_lines.append(line)

    flush()
    return blocks


def assign_chunk_ids(source_file: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    assigned_entries: list[dict[str, Any]] = []
    for index, entry in enumerate(entries, start=1):
        item = dict(entry)
        item["chunk_id"] = f"{Path(source_file).stem}-{index:04d}"
        assigned_entries.append(item)
    return assigned_entries


def rebalance_entries(source_file: str, base_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    final_entries: list[dict[str, Any]] = []

    for entry in base_entries:
        content = str(entry.get("content", "")).strip()
        if not content:
            continue

        if count_words(content) <= MAX_CHUNK_WORDS:
            final_entries.append(dict(entry))
            continue

        prefix_lines = build_prefix_lines(entry)
        content_lines = [normalize_line(line) for line in content.splitlines()]
        body_lines = strip_prefix_lines(content_lines, prefix_lines)
        semantic_blocks = build_semantic_blocks(body_lines)

        if not semantic_blocks:
            final_entries.append(dict(entry))
            continue

        grouped_blocks: list[list[str]] = []
        current_group: list[str] = []
        current_words = 0

        def flush_group() -> None:
            nonlocal current_group, current_words
            if current_group:
                grouped_blocks.append(current_group)
            current_group = []
            current_words = 0

        for block in semantic_blocks:
            block_words = count_words(block)
            if current_group and current_words >= MIN_CHUNK_WORDS and current_words + block_words > MAX_CHUNK_WORDS:
                flush_group()

            current_group.append(block)
            current_words += block_words

            if current_words >= TARGET_CHUNK_WORDS:
                flush_group()

        flush_group()

        if len(grouped_blocks) >= 2:
            last_words = count_words("\n\n".join(grouped_blocks[-1]))
            previous_words = count_words("\n\n".join(grouped_blocks[-2]))
            if last_words < MIN_CHUNK_WORDS and previous_words + last_words <= (MAX_CHUNK_WORDS + 80):
                grouped_blocks[-2].extend(grouped_blocks[-1])
                grouped_blocks.pop()

        for group in grouped_blocks:
            chunk_lines = [*prefix_lines, *group]
            chunk_content = "\n".join(line for line in chunk_lines if line).strip()
            if not chunk_content:
                continue
            item = dict(entry)
            item["content"] = chunk_content
            item["status"] = "partial" if UNREADABLE_PLACEHOLDER in chunk_content else "complete"
            final_entries.append(item)

    return final_entries


def build_notes(
    stats: ProcessingStats,
    title_source: str,
    partial_chunks: int,
    qa_summary: ChunkQaSummary,
) -> list[str]:
    notes: list[str] = []
    notes.append(
        "العنوان تم التقاطه من الحقول التعريفية."
        if title_source == "metadata"
        else "العنوان تم التقاطه من بداية النص."
        if title_source == "content"
        else "العنوان تم اشتقاقه من اسم الملف."
    )
    if stats.metadata_removed:
        notes.append(f"تم حذف {stats.metadata_removed} سطرًا من البيانات التعريفية المكررة.")
    if stats.page_noise_removed:
        notes.append(f"تم حذف {stats.page_noise_removed} سطرًا من أرقام الصفحات أو الفواصل.")
    if stats.repeated_headers_removed:
        notes.append(f"تم حذف {stats.repeated_headers_removed} سطرًا من الترويسات المكررة.")
    if stats.duplicate_lines_removed:
        notes.append(f"تم حذف {stats.duplicate_lines_removed} سطرًا مكررًا.")
    if stats.unreadable_lines_normalized:
        notes.append(
            f"تم توحيد {stats.unreadable_lines_normalized} موضعًا غير واضح إلى {UNREADABLE_PLACEHOLDER}."
        )
    if partial_chunks:
        notes.append(f"يوجد {partial_chunks} مقطعًا بحالة partial.")
    if qa_summary.heading_only_removed:
        notes.append(f"تم استبعاد {qa_summary.heading_only_removed} مقطعًا كان عبارة عن عناوين فقط.")
    if qa_summary.duplicate_chunks_removed:
        notes.append(f"تم استبعاد {qa_summary.duplicate_chunks_removed} مقطعًا مكررًا مطابقًا.")
    if qa_summary.tiny_chunks_flagged:
        notes.append(f"تم وسم {qa_summary.tiny_chunks_flagged} مقطعًا قصيرًا منخفض الإشارة للمراجعة.")
    if qa_summary.missing_metadata_flagged:
        notes.append(f"تم وسم {qa_summary.missing_metadata_flagged} مقطعًا بنقص في محددات التتبع أو العنوان.")
    if not any(
        (
            stats.metadata_removed,
            stats.page_noise_removed,
            stats.repeated_headers_removed,
            stats.duplicate_lines_removed,
            stats.unreadable_lines_normalized,
            partial_chunks,
            qa_summary.heading_only_removed,
            qa_summary.duplicate_chunks_removed,
            qa_summary.tiny_chunks_flagged,
            qa_summary.missing_metadata_flagged,
        )
    ):
        notes.append("لم يتم رصد ضوضاء ملحوظة تتطلب تنظيفًا إضافيًا.")
    return notes


def compute_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_processed_hashes(existing_manifest_documents: list[dict[str, Any]]) -> set[str]:
    hashes: set[str] = set()
    for document in existing_manifest_documents:
        source_hash = document.get("source_hash")
        cleaned_hash = document.get("cleaned_hash")
        if isinstance(source_hash, str) and source_hash:
            hashes.add(source_hash)
        if isinstance(cleaned_hash, str) and cleaned_hash:
            hashes.add(cleaned_hash)
    return hashes


def load_existing_entries() -> list[dict[str, Any]]:
    if not OUTPUT_JSONL_PATH.exists():
        return []

    entries: list[dict[str, Any]] = []
    with OUTPUT_JSONL_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                entries.append(json.loads(stripped))
    return entries


def load_existing_manifest_documents(existing_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    source_to_doc_type: dict[str, str] = {}
    for entry in existing_entries:
        source_to_doc_type.setdefault(entry.get("source_file", ""), entry.get("doc_type", "regulation"))

    if MANIFEST_PATH.exists():
        try:
            manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            documents = manifest.get("documents", [])
            if isinstance(documents, list):
                normalized_documents = []
                for item in documents:
                    if not isinstance(item, dict):
                        continue
                    normalized_item = dict(item)
                    normalized_item.setdefault(
                        "doc_type",
                        source_to_doc_type.get(normalized_item.get("source_file", ""), "regulation"),
                    )
                    normalized_documents.append(normalized_item)
                return normalized_documents
        except Exception:
            pass

    manifest_documents: list[dict[str, Any]] = []
    by_source: dict[str, list[dict[str, Any]]] = {}
    for entry in existing_entries:
        by_source.setdefault(entry.get("source_file", ""), []).append(entry)

    for source_file in sorted(by_source):
        source_entries = by_source[source_file]
        document_title = source_entries[0].get("document_title", Path(source_file).stem)
        partial_chunks = sum(1 for entry in source_entries if entry.get("status") == "partial")
        manifest_documents.append(
            {
                "source_file": source_file,
                "detected_title": document_title,
                "doc_type": source_entries[0].get("doc_type", "regulation"),
                "language": source_entries[0].get("language", ""),
                "number_of_chunks": len(source_entries),
                "status": "partial" if partial_chunks else "complete",
                "source_hash": "",
                "cleaned_hash": "",
                "notes": ["تم تحميل هذا الملف من المخرجات الحالية دون إعادة معالجته."],
            }
        )

    return manifest_documents


def list_raw_source_files() -> list[str]:
    ensure_directories()
    return [
        path.name
        for path in sorted(RAW_DIR.iterdir())
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    ]


def load_raw_documents(skip_hashes: set[str] | None = None) -> list[dict[str, Any]]:
    ensure_directories()
    documents: list[dict[str, Any]] = []
    skip_hashes = skip_hashes or set()

    for path in sorted(RAW_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        raw_text = path.read_text(encoding="utf-8", errors="replace")
        if not raw_text.strip():
            continue

        source_hash = compute_text_hash(raw_text)
        if source_hash in skip_hashes:
            continue

        preprocessed_text = preprocess_raw_text(raw_text)
        if not preprocessed_text.strip():
            continue

        raw_lines = preprocessed_text.splitlines()
        metadata, content_lines = extract_front_matter(raw_lines)
        document_title, title_source = detect_title(metadata, content_lines, path.name)
        cleaned_lines, stats = clean_lines(content_lines, title=document_title)
        cleaned_source_text = "\n".join(cleaned_lines).strip()
        cleaned_hash = compute_text_hash(cleaned_source_text)
        if cleaned_hash in skip_hashes:
            continue

        doc_type = detect_doc_type(path.name, document_title, cleaned_source_text)
        document_language = detect_document_language(metadata, path.name, document_title, cleaned_source_text)
        if cleaned_lines and is_title_like(cleaned_lines[0], document_title):
            cleaned_lines.pop(0)
            while cleaned_lines and cleaned_lines[0] == "":
                cleaned_lines.pop(0)

        base_entries = rebalance_entries(
            path.name,
            build_entries(path.name, document_title, doc_type, document_language, cleaned_lines),
        )
        entries, qa_summary = apply_chunk_qa(path.name, base_entries)
        partial_chunks = sum(1 for entry in entries if entry["status"] == "partial")
        manifest_entry = {
            "source_file": path.name,
            "detected_title": document_title,
            "doc_type": doc_type,
            "language": document_language,
            "number_of_chunks": len(entries),
            "source_hash": source_hash,
            "cleaned_hash": cleaned_hash,
            "status": "partial" if partial_chunks else "complete",
            "qa_summary": {
                "heading_only_removed": qa_summary.heading_only_removed,
                "duplicate_chunks_removed": qa_summary.duplicate_chunks_removed,
                "tiny_chunks_flagged": qa_summary.tiny_chunks_flagged,
                "partial_chunks_flagged": qa_summary.partial_chunks_flagged,
                "missing_metadata_flagged": qa_summary.missing_metadata_flagged,
            },
            "notes": build_notes(
                stats,
                title_source=title_source,
                partial_chunks=partial_chunks,
                qa_summary=qa_summary,
            ),
        }

        documents.append(
            {
                "source_file": path.name,
                "document_title": document_title,
                "metadata": metadata,
                "entries": entries,
                "manifest": manifest_entry,
            }
        )

    return documents


def save_processed_output(
    existing_entries: list[dict[str, Any]],
    existing_manifest_documents: list[dict[str, Any]],
    new_documents: list[dict[str, Any]],
    active_sources: list[str],
) -> tuple[int, int, int]:
    ensure_directories()
    active_source_set = set(active_sources)
    replaced_sources = {document["source_file"] for document in new_documents}
    new_entries = [entry for document in new_documents for entry in document["entries"]]
    preserved_entries = [
        entry
        for entry in existing_entries
        if entry.get("source_file") in active_source_set and entry.get("source_file") not in replaced_sources
    ]
    all_entries = [*preserved_entries, *new_entries]

    manifest_by_source: dict[str, dict[str, Any]] = {}
    for item in existing_manifest_documents:
        source_file = item.get("source_file", "")
        if source_file and source_file in active_source_set and source_file not in replaced_sources:
            manifest_by_source[source_file] = dict(item)

    for document in new_documents:
        manifest_item = dict(document["manifest"])
        source_file = manifest_item.get("source_file", "")
        if source_file:
            manifest_by_source[source_file] = manifest_item

    manifest_documents = [manifest_by_source[source] for source in active_sources if source in manifest_by_source]

    with OUTPUT_JSONL_PATH.open("w", encoding="utf-8") as file:
        for entry in all_entries:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    manifest = {
        "output_file": str(OUTPUT_JSONL_PATH.relative_to(BASE_DIR)),
        "document_count": len(manifest_documents),
        "chunk_count": len(all_entries),
        "documents": manifest_documents,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return len(new_documents), len(new_entries), len(all_entries)


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(
        description="Process Arabic university regulations text files into JSONL entries for RAG."
    )
    parser.add_argument(
        "--full-rebuild",
        action="store_true",
        help="Reprocess all files in data/raw and regenerate the processed outputs from scratch.",
    )
    args = parser.parse_args()

    existing_entries = [] if args.full_rebuild else load_existing_entries()
    existing_manifest_documents = (
        [] if args.full_rebuild else load_existing_manifest_documents(existing_entries)
    )
    active_sources = list_raw_source_files()
    existing_sources = {
        document.get("source_file", "")
        for document in existing_manifest_documents
        if document.get("source_file")
    }
    processed_hashes = extract_processed_hashes(existing_manifest_documents)

    documents = load_raw_documents(skip_hashes=processed_hashes if not args.full_rebuild else set())
    if not documents:
        if args.full_rebuild and not active_sources:
            print("No UTF-8 .txt files were found in data/raw.")
            return
        removed_sources = existing_sources - set(active_sources)
        if removed_sources:
            document_count, new_chunk_count, total_chunk_count = save_processed_output(
                existing_entries,
                existing_manifest_documents,
                [],
                active_sources,
            )
            print(f"Pruned {len(removed_sources)} stale source file(s) from processed output.")
            print(f"Processed output now contains {total_chunk_count} total chunk(s).")
            print(f"Saved JSONL to {OUTPUT_JSONL_PATH}")
            print(f"Saved manifest to {MANIFEST_PATH}")
            return
        print("No new UTF-8 .txt files were detected in data/raw.")
        print(f"Processed output remains at {len(existing_entries)} chunk(s).")
        return

    document_count, new_chunk_count, total_chunk_count = save_processed_output(
        existing_entries,
        existing_manifest_documents,
        documents,
        active_sources,
    )
    print(f"Processed {document_count} new source file(s) into {new_chunk_count} new JSONL entries.")
    print(f"Processed output now contains {total_chunk_count} total chunk(s).")
    for document in documents:
        manifest = document["manifest"]
        print(
            f"- {manifest['source_file']} | doc_type={manifest['doc_type']} | chunks={manifest['number_of_chunks']}"
        )
    print(f"Saved JSONL to {OUTPUT_JSONL_PATH}")
    print(f"Saved manifest to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
