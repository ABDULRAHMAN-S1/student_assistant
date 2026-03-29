from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

try:
    from app.retrieve import (
        BASE_DIR,
        BUILD_INFO_PATH,
        CHUNKS_PATH,
        COLLECTION_NAME,
        EMBEDDING_MODEL_NAME,
        NO_OP_TELEMETRY_IMPL,
        VECTORDB_DIR,
        build_chunk_sync_hash,
        build_display_title,
        build_processed_state_summary,
        build_vector_metadata_snapshot,
        clean_display_section,
        get_embedding_model,
    )
except ImportError:
    from retrieve import (  # type: ignore
        BASE_DIR,
        BUILD_INFO_PATH,
        CHUNKS_PATH,
        COLLECTION_NAME,
        EMBEDDING_MODEL_NAME,
        NO_OP_TELEMETRY_IMPL,
        VECTORDB_DIR,
        build_chunk_sync_hash,
        build_display_title,
        build_processed_state_summary,
        build_vector_metadata_snapshot,
        clean_display_section,
        get_embedding_model,
    )


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

    chunk_ids = [str(chunk.get("chunk_id", "")) for chunk in chunks]
    if not chunk_ids or any(not chunk_id for chunk_id in chunk_ids):
        raise RuntimeError("Processed chunks contain missing chunk IDs.")
    if len(set(chunk_ids)) != len(chunk_ids):
        raise RuntimeError("Processed chunks contain duplicate chunk IDs. Rebuild processed output first.")
    return chunks


def batched(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [items[index : index + batch_size] for index in range(0, len(items), batch_size)]


def compute_content_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def build_chunk_metadata(item: dict[str, Any]) -> dict[str, Any]:
    return {
        **build_vector_metadata_snapshot(item),
        "content_hash": compute_content_hash(item.get("content", "")),
        "sync_hash": build_chunk_sync_hash(item),
    }


def get_existing_chunk_state(collection: Any) -> dict[str, str]:
    try:
        total = int(collection.count())
    except Exception:
        return {}

    if total <= 0:
        return {}

    page_size = 512
    existing_state: dict[str, str] = {}
    for offset in range(0, total, page_size):
        result = collection.get(limit=page_size, offset=offset, include=["documents", "metadatas"])
        ids = result.get("ids", []) if isinstance(result, dict) else []
        documents = result.get("documents", []) if isinstance(result, dict) else []
        metadatas = result.get("metadatas", []) if isinstance(result, dict) else []
        for index, item in enumerate(ids):
            if not isinstance(item, str):
                continue
            metadata = metadatas[index] if index < len(metadatas) and isinstance(metadatas[index], dict) else {}
            stored_hash = metadata.get("sync_hash") if isinstance(metadata.get("sync_hash"), str) else ""
            if not stored_hash:
                document = documents[index] if index < len(documents) and isinstance(documents[index], str) else ""
                stored_hash = build_chunk_sync_hash(
                    {
                        "chunk_id": item,
                        "content": document,
                        "source": metadata.get("source", ""),
                        "document_title": metadata.get("document_title", ""),
                        "section": metadata.get("section", ""),
                        "article": metadata.get("article", ""),
                        "doc_type": metadata.get("doc_type", ""),
                        "language": metadata.get("language", ""),
                        "status": metadata.get("status", ""),
                    }
                )
            existing_state[item] = stored_hash
    return existing_state


def build_info_payload(
    *,
    chunk_count: int,
    processed_sync_hash: str,
    new_chunks_added: int,
    updated_chunks: int,
    deleted_chunks: int,
    rebuild: bool,
    vector_count: int,
) -> dict[str, Any]:
    return {
        "collection_name": COLLECTION_NAME,
        "embedding_model": EMBEDDING_MODEL_NAME,
        "chunk_count": chunk_count,
        "processed_sync_hash": processed_sync_hash,
        "new_chunks_added": new_chunks_added,
        "updated_chunks": updated_chunks,
        "deleted_chunks": deleted_chunks,
        "rebuild": rebuild,
        "vector_count": vector_count,
        "vectordb_path": str(VECTORDB_DIR.relative_to(BASE_DIR)),
    }


def write_build_info(build_info: dict[str, Any]) -> None:
    BUILD_INFO_PATH.write_text(
        json.dumps(build_info, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def reset_vectordb_directory() -> None:
    keep_gitkeep = (VECTORDB_DIR / ".gitkeep").exists()
    if VECTORDB_DIR.exists():
        shutil.rmtree(VECTORDB_DIR)
    VECTORDB_DIR.mkdir(parents=True, exist_ok=True)
    if keep_gitkeep:
        (VECTORDB_DIR / ".gitkeep").touch()


def build_vector_store(rebuild: bool = False, batch_size: int = 32) -> dict[str, Any]:
    chunks = load_chunks()
    if not chunks:
        raise RuntimeError("No chunks found in the processed file.")
    processed_state = build_processed_state_summary(chunks)

    if rebuild:
        reset_vectordb_directory()
    else:
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
    new_chunks_added = len(chunks)
    updated_chunks = 0
    deleted_chunks = 0
    if not rebuild:
        existing_state = get_existing_chunk_state(collection)
        current_ids = {item["chunk_id"] for item in chunks}
        stale_ids = [chunk_id for chunk_id in existing_state if chunk_id not in current_ids]
        if stale_ids:
            collection.delete(ids=stale_ids)
            deleted_chunks = len(stale_ids)

        chunks_to_embed = []
        new_chunks_added = 0
        updated_chunks = 0
        for item in chunks:
            chunk_id = item["chunk_id"]
            sync_hash = build_chunk_sync_hash(item)
            stored_hash = existing_state.get(chunk_id)
            if stored_hash is None:
                chunks_to_embed.append(item)
                new_chunks_added += 1
                continue
            if stored_hash != sync_hash:
                chunks_to_embed.append(item)
                updated_chunks += 1

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
            metadatas=[build_chunk_metadata(item) for item in batch],
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
        processed_sync_hash=processed_state["sync_hash"],
        new_chunks_added=new_chunks_added,
        updated_chunks=updated_chunks,
        deleted_chunks=deleted_chunks,
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
