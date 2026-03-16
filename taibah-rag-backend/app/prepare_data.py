from __future__ import annotations

import argparse
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
CLAUSE_RE = re.compile(r"^(?P<label>(?:\d+|[" + ARABIC_DIGITS + r"]+|[أ-ي]))[.)-]\s+.+$")
DEFINITION_RE = re.compile(r"^(?P<label>[^:]{2,70}):\s+.+$")


@dataclass
class ProcessingStats:
    metadata_removed: int = 0
    page_noise_removed: int = 0
    repeated_headers_removed: int = 0
    duplicate_lines_removed: int = 0
    unreadable_lines_normalized: int = 0


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


def canonical_line(line: str) -> str:
    normalized = normalize_line(line)
    normalized = re.sub(r"[^\w\u0600-\u06FF" + ARABIC_DIGITS + r"]+", "", normalized)
    return normalized.lower()


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
    arabic_or_digit_count = len(re.findall(r"[\u0600-\u06FF0-9" + ARABIC_DIGITS + r"]", line))
    suspicious_count = len(re.findall(r"[^\u0600-\u06FF0-9" + ARABIC_DIGITS + r"\s\[\]\(\)\-_/.:،؛؟!]", line))
    return arabic_or_digit_count == 0 and suspicious_count >= 4


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


def build_entries(source_file: str, document_title: str, lines: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    context = DocumentContext()
    current_lines: list[str] = []
    current_section = ""
    current_article = ""
    chunk_index = 1

    def flush() -> None:
        nonlocal current_lines, current_section, current_article, chunk_index
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
        entries.append(
            {
                "source_file": source_file,
                "document_title": document_title,
                "doc_type": "regulation",
                "language": "ar",
                "section": current_section,
                "article": current_article,
                "chunk_id": f"{Path(source_file).stem}-{chunk_index:04d}",
                "content": content,
                "status": status,
            }
        )
        chunk_index += 1
        current_lines = []
        current_section = compose_section(context)
        current_article = context.article

    def start_chunk(prefix: list[str], article_value: str = "") -> None:
        nonlocal current_lines, current_section, current_article
        current_section = compose_section(context)
        current_article = article_value
        current_lines = prefix.copy()

    for index, line in enumerate(lines):
        if not line:
            if current_lines and current_lines[-1] != "":
                current_lines.append("")
            continue

        next_line = next_nonempty_line(lines, index + 1)

        if CHAPTER_RE.match(line):
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

        if not context.article and (SECTION_RE.match(line) or is_standalone_heading(line, next_line) or is_colon_heading(line, next_line)):
            flush()
            context.section = line.rstrip(":：")
            context.article = ""
            continue

        if ARTICLE_RE.match(line):
            flush()
            context.article = line.rstrip()
            start_chunk(build_prefix(context, context.article), article_value=context.article)
            continue

        if not context.article and context.section and CLAUSE_RE.match(line):
            flush()
            clause_label = extract_clause_label(line)
            start_chunk(
                build_prefix(context) + [line],
                article_value=f"البند {clause_label}" if clause_label else "",
            )
            continue

        if not context.article and DEFINITION_RE.match(line) and not CLAUSE_RE.match(line):
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


def build_notes(stats: ProcessingStats, title_source: str, partial_chunks: int) -> list[str]:
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
    if not any(
        (
            stats.metadata_removed,
            stats.page_noise_removed,
            stats.repeated_headers_removed,
            stats.duplicate_lines_removed,
            stats.unreadable_lines_normalized,
            partial_chunks,
        )
    ):
        notes.append("لم يتم رصد ضوضاء ملحوظة تتطلب تنظيفًا إضافيًا.")
    return notes


def load_raw_documents() -> list[dict[str, Any]]:
    ensure_directories()
    documents: list[dict[str, Any]] = []

    for path in sorted(RAW_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        raw_text = path.read_text(encoding="utf-8", errors="replace")
        raw_lines = raw_text.splitlines()
        metadata, content_lines = extract_front_matter(raw_lines)
        document_title, title_source = detect_title(metadata, content_lines, path.name)
        cleaned_lines, stats = clean_lines(content_lines, title=document_title)
        if cleaned_lines and is_title_like(cleaned_lines[0], document_title):
            cleaned_lines.pop(0)
            while cleaned_lines and cleaned_lines[0] == "":
                cleaned_lines.pop(0)

        entries = build_entries(path.name, document_title, cleaned_lines)
        partial_chunks = sum(1 for entry in entries if entry["status"] == "partial")
        manifest_entry = {
            "source_file": path.name,
            "detected_title": document_title,
            "number_of_chunks": len(entries),
            "status": "partial" if partial_chunks else "complete",
            "notes": build_notes(stats, title_source=title_source, partial_chunks=partial_chunks),
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


def save_processed_output(documents: list[dict[str, Any]]) -> tuple[int, int]:
    ensure_directories()
    all_entries = [entry for document in documents for entry in document["entries"]]
    manifest_documents = [document["manifest"] for document in documents]

    with OUTPUT_JSONL_PATH.open("w", encoding="utf-8") as file:
        for entry in all_entries:
            file.write(json.dumps(entry, ensure_ascii=False) + "\n")

    manifest = {
        "output_file": str(OUTPUT_JSONL_PATH.relative_to(BASE_DIR)),
        "document_count": len(documents),
        "chunk_count": len(all_entries),
        "documents": manifest_documents,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return len(documents), len(all_entries)


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(
        description="Process Arabic university regulations text files into JSONL entries for RAG."
    )
    parser.parse_args()

    documents = load_raw_documents()
    if not documents:
        print("No UTF-8 .txt files were found in data/raw.")
        return

    document_count, chunk_count = save_processed_output(documents)
    print(f"Processed {document_count} source file(s) into {chunk_count} JSONL entries.")
    print(f"Saved JSONL to {OUTPUT_JSONL_PATH}")
    print(f"Saved manifest to {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
