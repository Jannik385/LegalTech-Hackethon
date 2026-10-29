"""RAG service — Retrieval-Augmented Generation for Mietrecht law texts.

Two public functions:
  ingest_law_texts() — chunk law text files and index into ChromaDB (run once).
  retrieve(query, top_k) — return the top-k most relevant chunks for a query.

Embeddings are computed locally with sentence-transformers
(intfloat/multilingual-e5-large), which handles German legal text well.
ChromaDB is persisted to CHROMA_PATH (default: backend/.chromadb/).
"""

from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional imports — app starts gracefully even if these are not installed yet
# ---------------------------------------------------------------------------
try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    _RAG_AVAILABLE = True
except ImportError:
    _RAG_AVAILABLE = False

from backend.config import CHROMA_PATH, EMBEDDING_MODEL, LAW_TEXTS_PATH

# ---------------------------------------------------------------------------
# Module-level singletons (initialised lazily on first use)
# ---------------------------------------------------------------------------
_client: "chromadb.PersistentClient | None" = None
_collection: "chromadb.Collection | None" = None
_embedder: "SentenceTransformer | None" = None

COLLECTION_NAME = "mietrecht_law"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_embedder() -> "SentenceTransformer":
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer(EMBEDDING_MODEL)
    return _embedder


def _get_collection() -> "chromadb.Collection":
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _chunk_text(text: str, chunk_size: int = 400, overlap: int = 80) -> list[str]:
    """Split text into overlapping chunks by word count."""
    words = text.split()
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap
    return chunks


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest_law_texts(force: bool = False) -> int:
    """Index all .md files in LAW_TEXTS_PATH into ChromaDB.

    Skips ingestion if the collection already has documents, unless
    force=True.  Returns the number of chunks indexed.
    """
    if not _RAG_AVAILABLE:
        return 0

    collection = _get_collection()

    if not force and collection.count() > 0:
        return collection.count()

    embedder = _get_embedder()
    law_dir = Path(LAW_TEXTS_PATH)
    if not law_dir.exists():
        return 0

    # Infer category from filename prefix
    _FILENAME_CATEGORY = {
        "formell": "formellrechtlich",
        "materiell": "materiellrechtlich",
        "hauptverhandlung": "hauptverhandlung",
    }

    all_texts: list[str] = []
    all_ids: list[str] = []
    all_metadatas: list[dict] = []

    for md_file in sorted(law_dir.glob("*.md")):
        raw = md_file.read_text(encoding="utf-8")
        category = "materiellrechtlich"
        for key, cat in _FILENAME_CATEGORY.items():
            if key in md_file.stem.lower():
                category = cat
                break

        chunks = _chunk_text(raw)
        for i, chunk in enumerate(chunks):
            chunk_id = f"{md_file.stem}_{i}"
            # Extract a rough paragraph label from the first line of the chunk
            first_line = chunk.split("\n")[0][:80]
            all_texts.append(chunk)
            all_ids.append(chunk_id)
            all_metadatas.append({"category": category, "source": md_file.name, "paragraph": first_line})

    if not all_texts:
        return 0

    # Embed in batches of 64 to avoid OOM on large corpora
    batch_size = 64
    all_embeddings: list[list[float]] = []
    for i in range(0, len(all_texts), batch_size):
        batch = all_texts[i : i + batch_size]
        # multilingual-e5 requires a query/passage prefix
        prefixed = [f"passage: {t}" for t in batch]
        vecs = embedder.encode(prefixed, normalize_embeddings=True).tolist()
        all_embeddings.extend(vecs)

    # Upsert — safe to call multiple times
    collection.upsert(
        ids=all_ids,
        embeddings=all_embeddings,
        documents=all_texts,
        metadatas=all_metadatas,
    )

    return len(all_texts)


def retrieve(query: str, top_k: int = 5) -> list[str]:
    """Return the top-k most relevant law chunks for the given query.

    Returns an empty list if RAG is unavailable or the collection is empty.
    Each returned string is a raw text chunk suitable for prompt injection.
    """
    if not _RAG_AVAILABLE:
        return []

    collection = _get_collection()
    if collection.count() == 0:
        return []

    embedder = _get_embedder()
    query_vec = embedder.encode(f"query: {query}", normalize_embeddings=True).tolist()

    results = collection.query(
        query_embeddings=[query_vec],
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas"],
    )

    chunks: list[str] = []
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    for doc, meta in zip(docs, metas):
        src = meta.get("source", "")
        cat = meta.get("category", "")
        chunks.append(f"[{cat} | {src}]\n{doc}")

    return chunks
