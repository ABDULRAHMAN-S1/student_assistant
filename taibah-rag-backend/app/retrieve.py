from __future__ import annotations

import argparse
import json
import os
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROCESSED_DIR = DATA_DIR / "processed"
VECTORDB_DIR = DATA_DIR / "vectordb"
CHUNKS_PATH = PROCESSED_DIR / "taibah_regulations.jsonl"
COLLECTION_NAME = os.getenv("VECTOR_COLLECTION_NAME", "university_regulations")
EMBEDDING_MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
)
NO_OP_TELEMETRY_IMPL = "app.chroma_telemetry.NoOpTelemetryClient"
ARABIC_PATTERN = re.compile(r"[\u0600-\u06FF]")
ARABIC_DIACRITICS_PATTERN = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
NON_WORD_PATTERN = re.compile(r"[^\w\s\u0600-\u06FF]+")
SPACE_PATTERN = re.compile(r"\s+")
TOKEN_PATTERN = re.compile(r"[\w\u0600-\u06FF]+")
PUNCTUATION_TRANSLATION = str.maketrans(
    {
        "؟": " ",
        "،": " ",
        "؛": " ",
        ":": " ",
        "/": " ",
        "\\": " ",
        "-": " ",
        "_": " ",
        "(": " ",
        ")": " ",
        "[": " ",
        "]": " ",
        "{": " ",
        "}": " ",
        "\"": " ",
        "'": " ",
    }
)
ARABIC_EMBEDDING_TRANSLATION = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
    }
)
ARABIC_MATCHING_TRANSLATION = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "ة": "ه",
    }
)
ARABIC_STOPWORDS = {
    "ما",
    "متى",
    "هل",
    "في",
    "من",
    "على",
    "الى",
    "إلى",
    "عن",
    "او",
    "أو",
    "ثم",
    "اذا",
    "إذا",
    "كيف",
    "يمكن",
    "استطيع",
    "أستطيع",
    "يسمح",
    "داخل",
    "هذه",
    "هذا",
    "ذلك",
    "تلك",
    "مع",
    "كل",
    "بعد",
    "قبل",
    "عند",
    "لماذا",
}
IMPORTANT_LEGAL_STEMS = {
    "غش",
    "عقوب",
    "تدخين",
    "انسحاب",
    "سكن",
    "اسكان",
    "شرط",
    "تحويل",
    "تخصص",
    "حرمان",
    "غياب",
    "عذر",
    "تصوير",
    "محاضر",
    "حد",
    "اعلي",
    "اعلى",
    "عبء",
    "ساع",
    "قرض",
    "قروض",
    "مكاف",
    "اعان",
    "نادي",
    "رياض",
    "ملعب",
}
BROAD_ACADEMIC_STEMS = {
    "اختبار",
    "نهائي",
}
IMPORTANT_LEGAL_PHRASES = (
    "الاختبار النهائي",
    "الاختبارات النهائيه",
    "الاختبارات النهائية",
    "السكن الطلابي",
    "السكن الجامعي",
    "شروط القبول بالاسكان الطلابي",
    "شروط القبول بالإسكان الطلابي",
    "الحد الاعلى للعبء الدراسي",
    "الحد الأعلى للعبء الدراسي",
    "تصوير المحاضرات",
    "قواعد السلوك والانضباط",
)


def detect_language(text: str) -> str:
    return "ar" if ARABIC_PATTERN.search(text or "") else "en"


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def normalize_text(text: str, *, for_matching: bool = False) -> str:
    normalized = (text or "").strip()
    if not normalized:
        return ""

    normalized = ARABIC_DIACRITICS_PATTERN.sub("", normalized)
    normalized = normalized.replace("ـ", "")
    normalized = normalized.translate(PUNCTUATION_TRANSLATION)

    if detect_language(normalized) == "ar":
        translation = ARABIC_MATCHING_TRANSLATION if for_matching else ARABIC_EMBEDDING_TRANSLATION
        normalized = normalized.translate(translation)

    normalized = NON_WORD_PATTERN.sub(" ", normalized)
    normalized = SPACE_PATTERN.sub(" ", normalized).strip().lower()
    return normalized


def normalize_query(query: str) -> str:
    return normalize_text(query, for_matching=False)


def normalize_for_matching(text: str) -> str:
    return normalize_text(text, for_matching=True)


def tokenize_text(text: str) -> list[str]:
    return [token for token in TOKEN_PATTERN.findall(normalize_for_matching(text)) if token]


def strip_common_prefix(token: str) -> str:
    prefixes = ("وال", "بال", "كال", "فال", "لل", "ال", "و", "ف", "ب", "ك", "ل")
    for prefix in prefixes:
        if token.startswith(prefix) and len(token) - len(prefix) >= 3:
            return token[len(prefix) :]
    return token


def strip_common_suffix(token: str) -> str:
    suffixes = ("يات", "ات", "ها", "هم", "كم", "نا", "ه", "ا")
    for suffix in suffixes:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)]
    return token


def light_stem(token: str) -> str:
    stem = strip_common_prefix(token)
    stem = strip_common_suffix(stem)
    return stem or token


def build_metadata(entry: dict[str, Any]) -> dict[str, Any]:
    section = entry.get("section", "")
    article = entry.get("article", "")
    title = article or section or entry.get("document_title", "")
    return {
        "source": entry.get("source_file", ""),
        "document_title": entry.get("document_title", ""),
        "title": title,
        "section": section,
        "article": article,
        "doc_type": entry.get("doc_type", ""),
        "language": entry.get("language", ""),
        "status": entry.get("status", ""),
    }


@lru_cache(maxsize=1)
def get_chunk_records() -> list[dict[str, Any]]:
    if not CHUNKS_PATH.exists():
        raise RuntimeError("Processed chunks not found. Run `python -m app.prepare_data` first.")

    records: list[dict[str, Any]] = []
    with CHUNKS_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if not stripped:
                continue

            entry = json.loads(stripped)
            metadata = build_metadata(entry)
            metadata_text = " ".join(
                value for value in (metadata["document_title"], metadata["section"], metadata["article"]) if value
            )
            normalized_content = normalize_for_matching(entry.get("content", ""))
            normalized_metadata = normalize_for_matching(metadata_text)
            records.append(
                {
                    "id": entry.get("chunk_id", ""),
                    "content": entry.get("content", ""),
                    "metadata": metadata,
                    "normalized_content": normalized_content,
                    "normalized_metadata": normalized_metadata,
                    "content_stems": {light_stem(token) for token in tokenize_text(entry.get("content", ""))},
                    "metadata_stems": {light_stem(token) for token in tokenize_text(metadata_text)},
                }
            )
    return records


@lru_cache(maxsize=1)
def get_chunk_record_map() -> dict[str, dict[str, Any]]:
    return {record["id"]: record for record in get_chunk_records()}


def build_query_profile(query: str) -> dict[str, Any]:
    normalized_query = normalize_for_matching(query)
    tokens = []
    stems = []
    seen_tokens: set[str] = set()
    seen_stems: set[str] = set()

    for token in tokenize_text(query):
        if len(token) < 2 or token in ARABIC_STOPWORDS:
            continue
        if token not in seen_tokens:
            seen_tokens.add(token)
            tokens.append(token)
        stem = light_stem(token)
        if len(stem) >= 2 and stem not in seen_stems:
            seen_stems.add(stem)
            stems.append(stem)

    phrases = []
    for phrase in IMPORTANT_LEGAL_PHRASES:
        normalized_phrase = normalize_for_matching(phrase)
        if normalized_phrase in normalized_query:
            phrases.append(normalized_phrase)

    important_stems = [stem for stem in stems if stem in IMPORTANT_LEGAL_STEMS]
    broad_stems = [stem for stem in stems if stem in BROAD_ACADEMIC_STEMS]
    return {
        "normalized_query": normalized_query,
        "tokens": tokens,
        "stems": stems,
        "phrases": phrases,
        "important_stems": important_stems,
        "strong_stems": important_stems,
        "broad_stems": broad_stems,
    }


def infer_query_flags(query_profile: dict[str, Any]) -> dict[str, bool]:
    normalized_query = query_profile["normalized_query"]
    stems = set(query_profile["stems"])
    return {
        "housing": bool({"سكن", "اسكان", "اقام"} & stems)
        or any(phrase in normalized_query for phrase in ("السكن الطلابي", "السكن الجامعي", "الاسكان الطلابي")),
        "dress": bool({"زي", "مظهر", "عباي", "لبس"} & stems)
        or any(phrase in normalized_query for phrase in ("الزي الجامعي", "المظهر العام")),
    }


def infer_record_flags(record: dict[str, Any]) -> dict[str, bool]:
    metadata = record["metadata"]
    text = normalize_for_matching(
        " ".join(
            part
            for part in (
                metadata.get("document_title", ""),
                metadata.get("section", ""),
                metadata.get("article", ""),
            )
            if part
        )
    )
    return {
        "housing": any(term in text for term in ("اسكان", "سكن")),
        "dress": any(term in text for term in ("الزي", "مظهر")),
    }


def important_match_ratio(record: dict[str, Any], query_profile: dict[str, Any]) -> float:
    important_stems = query_profile["important_stems"]
    if not important_stems:
        return 0.0

    matched = sum(
        1
        for stem in important_stems
        if stem in record["content_stems"] or stem in record["metadata_stems"]
    )
    return matched / len(important_stems)


def lexical_match_score(record: dict[str, Any], query_profile: dict[str, Any]) -> float:
    if not query_profile["tokens"] and not query_profile["phrases"]:
        return 0.0

    content_text = record["normalized_content"]
    metadata_text = record["normalized_metadata"]
    content_stems = record["content_stems"]
    metadata_stems = record["metadata_stems"]

    score = 0.0
    max_score = 0.0

    for phrase in query_profile["phrases"]:
        max_score += 3.5
        if phrase in metadata_text:
            score += 3.5
        elif phrase in content_text:
            score += 3.0

    for token in query_profile["tokens"]:
        max_score += 1.4
        token_pattern = f" {token} "
        if token_pattern in f" {metadata_text} ":
            score += 1.4
        elif token_pattern in f" {content_text} ":
            score += 1.1

    for stem in query_profile["stems"]:
        max_score += 1.7
        stem_bonus = 0.5 if stem in IMPORTANT_LEGAL_STEMS else 0.0
        if stem in metadata_stems:
            score += 1.7 + stem_bonus
        elif stem in content_stems:
            score += 1.4 + stem_bonus

    important_stems = query_profile["important_stems"]
    if important_stems:
        max_score += 2.0
        matched_important = sum(
            1 for stem in important_stems if stem in content_stems or stem in metadata_stems
        )
        score += 2.0 * (matched_important / len(important_stems))

    if max_score <= 0.0:
        return 0.0
    return min(1.0, score / max_score)


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


@lru_cache(maxsize=1)
def get_chroma_client() -> chromadb.PersistentClient:
    VECTORDB_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(VECTORDB_DIR),
        settings=Settings(
            anonymized_telemetry=False,
            chroma_product_telemetry_impl=NO_OP_TELEMETRY_IMPL,
            chroma_telemetry_impl=NO_OP_TELEMETRY_IMPL,
        ),
    )


@lru_cache(maxsize=1)
def get_collection() -> Any:
    client = get_chroma_client()
    try:
        return client.get_collection(COLLECTION_NAME)
    except Exception as exc:
        message = (
            "Vector collection not found. Run `python -m app.prepare_data` and "
            "`python -m app.embed_store --rebuild` first."
        )
        raise RuntimeError(message) from exc


def semantic_search(query: str, top_k: int = 4) -> list[dict[str, Any]]:
    raw_query = (query or "").strip()
    if not raw_query:
        return []

    collection = get_collection()
    model = get_embedding_model()
    normalized_query = normalize_query(raw_query)
    query_embedding = model.encode(normalized_query, normalize_embeddings=True).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=max(1, top_k),
    )

    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    matches: list[dict[str, Any]] = []
    for doc_id, document, metadata, distance in zip(ids, documents, metadatas, distances):
        score = max(0.0, min(1.0, 1.0 - float(distance)))
        matches.append(
            {
                "id": doc_id,
                "content": document,
                "score": round(score, 4),
                "metadata": metadata or {},
            }
        )
    return matches


def lexical_search(
    query: str,
    top_k: int = 4,
    query_profile: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    raw_query = (query or "").strip()
    if not raw_query:
        return []

    query_profile = query_profile or build_query_profile(raw_query)
    if not query_profile["tokens"] and not query_profile["phrases"]:
        return []

    matches: list[dict[str, Any]] = []
    for record in get_chunk_records():
        score = lexical_match_score(record, query_profile)
        if score <= 0.0:
            continue
        matches.append(
            {
                "id": record["id"],
                "content": record["content"],
                "score": round(score, 4),
                "metadata": record["metadata"],
            }
        )

    matches.sort(key=lambda item: item["score"], reverse=True)
    return matches[: max(1, top_k)]


def combine_scores(semantic_score: float, lexical_score: float, *, prefer_lexical: bool) -> float:
    if lexical_score <= 0.0:
        return semantic_score
    if prefer_lexical:
        combined = (semantic_score * 0.58) + (lexical_score * 0.72)
        if lexical_score >= 0.6:
            combined += 0.08
    else:
        combined = max(semantic_score, (semantic_score * 0.82) + (lexical_score * 0.3))
    return max(0.0, min(1.0, combined))


def search(query: str, top_k: int = 4) -> list[dict[str, Any]]:
    raw_query = (query or "").strip()
    if not raw_query:
        return []

    candidate_limit = max(24, top_k * 12)
    semantic_matches = semantic_search(raw_query, top_k=candidate_limit)
    if detect_language(raw_query) != "ar":
        for match in semantic_matches:
            match["semantic_score"] = match["score"]
            match["lexical_score"] = 0.0
        return semantic_matches[:top_k]

    query_profile = build_query_profile(raw_query)
    lexical_matches = lexical_search(raw_query, top_k=candidate_limit, query_profile=query_profile)
    prefer_lexical = bool(query_profile["strong_stems"])
    query_flags = infer_query_flags(query_profile)
    record_map = get_chunk_record_map()

    combined_matches: dict[str, dict[str, Any]] = {}
    for match in semantic_matches:
        combined_matches[match["id"]] = {
            "id": match["id"],
            "content": match["content"],
            "metadata": match["metadata"],
            "semantic_score": match["score"],
            "lexical_score": 0.0,
        }

    for match in lexical_matches:
        item = combined_matches.setdefault(
            match["id"],
            {
                "id": match["id"],
                "content": match["content"],
                "metadata": match["metadata"],
                "semantic_score": 0.0,
                "lexical_score": 0.0,
            },
        )
        item["lexical_score"] = max(item["lexical_score"], match["score"])

    ranked = []
    for item in combined_matches.values():
        record = record_map.get(item["id"])
        if record is None:
            continue

        lexical_score = item["lexical_score"]
        semantic_score = item["semantic_score"]
        score = combine_scores(
            semantic_score,
            lexical_score,
            prefer_lexical=prefer_lexical,
        )
        match_ratio = important_match_ratio(record, query_profile)
        record_flags = infer_record_flags(record)

        if query_profile["important_stems"]:
            if match_ratio <= 0.0 and lexical_score < 0.22:
                continue
            if len(query_profile["important_stems"]) >= 2 and match_ratio < 0.34 and lexical_score < 0.45:
                score -= 0.14

        if record_flags["housing"] and not query_flags["housing"] and lexical_score < 0.55:
            score -= 0.12
        if record_flags["dress"] and not query_flags["dress"] and lexical_score < 0.55:
            score -= 0.16

        ranked.append(
            {
                "id": item["id"],
                "content": item["content"],
                "score": round(max(0.0, min(1.0, score)), 4),
                "semantic_score": round(semantic_score, 4),
                "lexical_score": round(lexical_score, 4),
                "metadata": item["metadata"],
            }
        )

    ranked.sort(
        key=lambda item: (
            item["score"],
            item["metadata"].get("article", ""),
            item["metadata"].get("section", ""),
        ),
        reverse=True,
    )
    return ranked[:top_k]


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Search the local regulations vector store.")
    parser.add_argument("question", help="Question to search for.")
    parser.add_argument("--top-k", type=int, default=4, help="Number of chunks to retrieve.")
    args = parser.parse_args()

    results = search(args.question, top_k=args.top_k)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
