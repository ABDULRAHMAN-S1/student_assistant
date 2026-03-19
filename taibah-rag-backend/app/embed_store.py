from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

try:
    from app.retrieve import (
        BASE_DIR,
        CHUNKS_PATH,
        COLLECTION_NAME,
        EMBEDDING_MODEL_NAME,
        NO_OP_TELEMETRY_IMPL,
        VECTORDB_DIR,
        build_display_title,
        clean_display_section,
        get_embedding_model,
    )
except ImportError:
    from retrieve import (  # type: ignore
        BASE_DIR,
        CHUNKS_PATH,
        COLLECTION_NAME,
        EMBEDDING_MODEL_NAME,
        NO_OP_TELEMETRY_IMPL,
        VECTORDB_DIR,
        build_display_title,
        clean_display_section,
        get_embedding_model,
    )


BUILD_INFO_PATH = VECTORDB_DIR / "build_info.json"


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def load_chunks() -> list[dict[str, Any]]:
    if not CHUNKS_PATH.exists():
        raise RuntimeError("Processed chunks not found. Run `python -m app.prepare_data` first.")

    chunks: list[dict[str, Any]] = []
    with CHUNKS_PATH.open("r", encoding="utf-8") as file:
        for line in file:
            stripped = line.strip()
            if stripped:
                chunks.append(json.loads(stripped))
    return chunks


def batched(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def get_existing_ids(collection: Any) -> set[str]:
    try:
        total = int(collection.count())
    except Exception:
        return set()

    if total <= 0:
        return set()

    page_size = 512
    existing_ids: set[str] = set()
    for offset in range(0, total, page_size):
        result = collection.get(limit=page_size, offset=offset, include=[])
        ids = result.get("ids", []) if isinstance(result, dict) else []
        existing_ids.update(item for item in ids if isinstance(item, str))
    return existing_ids


def build_info_payload(
    *,
    chunk_count: int,
    new_chunks_added: int,
    rebuild: bool,
    vector_count: int,
) -> dict[str, Any]:
    return {
        "collection_name": COLLECTION_NAME,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "chunk_count": chunk_count,
        "new_chunks_added": new_chunks_added,
        "rebuild": rebuild,
        "vector_count": vector_count,
        "vectordb_path": str(VECTORDB_DIR.relative_to(BASE_DIR)),
    }


def write_build_info(build_info: dict[str, Any]) -> None:
    BUILD_INFO_PATH.write_text(
        json.dumps(build_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_vector_store(rebuild: bool = False, batch_size: int = 32) -> dict[str, Any]:
    chunks = load_chunks()
    if not chunks:
        raise RuntimeError("No chunks found in the processed file.")

    VECTORDB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(
        path=str(VECTORDB_DIR),
        settings=Settings(
            anonymized_telemetry=False,
            chroma_product_telemetry_impl=NO_OP_TELEMETRY_IMPL,
            chroma_telemetry_impl=NO_OP_TELEMETRY_IMPL,
        ),
    )

    if rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    chunks_to_embed = chunks
    if not rebuild:
        existing_ids = get_existing_ids(collection)
        chunks_to_embed = [item for item in chunks if item["chunk_id"] not in existing_ids]

    if chunks_to_embed:
        model = get_embedding_model()

    for batch in batched(chunks_to_embed, batch_size=max(1, batch_size)):
        documents = [item["content"] for item in batch]
        embeddings = model.encode(
            documents,
            batch_size=max(1, min(batch_size, len(batch))),
            normalize_embeddings=True,
            show_progress_bar=False,
        ).tolist()
        collection.upsert(
            ids=[item["chunk_id"] for item in batch],
            documents=documents,
            metadatas=[
                {
                    "source": item["source_file"],
                    "document_title": item["document_title"],
                    "title": build_display_title(
                        document_title=item.get("document_title", ""),
                        article=item.get("article", ""),
                        section=item.get("section", ""),
                    ),
                    "section": clean_display_section(item.get("section", "")),
                    "article": item["article"],
                    "doc_type": item["doc_type"],
                    "language": item["language"],
                    "status": item["status"],
                }
                for item in batch
            ],
            embeddings=embeddings,
        )

    vector_count = int(collection.count())
    expected_count = len(chunks)
    if vector_count != expected_count:
        raise RuntimeError(
            "Vector store count mismatch after sync: "
            f"expected {expected_count} chunks from {Path(CHUNKS_PATH).name}, got {vector_count} vectors."
        )

    build_info = build_info_payload(
        chunk_count=expected_count,
        new_chunks_added=len(chunks_to_embed),
        rebuild=rebuild,
        vector_count=vector_count,
    )
    write_build_info(build_info)
    return build_info


def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(description="Embed processed chunks into a persistent vector store.")
    parser.add_argument("--rebuild", action="store_true", help="Delete and rebuild the collection.")
    parser.add_argument("--batch-size", type=int, default=32, help="Embedding batch size.")
    args = parser.parse_args()

    build_info = build_vector_store(rebuild=args.rebuild, batch_size=args.batch_size)
    print(json.dumps(build_info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
