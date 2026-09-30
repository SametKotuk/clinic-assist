"""Chunk'ları embedding'e çevirip Chroma'ya yazar."""
from __future__ import annotations

import chromadb

from src.config import settings
from src.ingest.chunking import Chunk
from src.ingest.embedder import Embedder


def get_collection(reset: bool = False, name: str | None = None):
    name = name or settings.collection
    client = chromadb.PersistentClient(path=str(settings.chroma_path))
    if reset:
        try:
            client.delete_collection(name)
        except Exception:
            pass  # koleksiyon yoksa sorun değil
    return client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})


def build_index(chunks: list[Chunk], embedder: Embedder, reset: bool = True,
                collection: str | None = None, use_header: bool = True) -> int:
    """İndeksi baştan kurar (idempotent). Yazılan chunk sayısını döndürür."""
    col = get_collection(reset=reset, name=collection)
    embeddings = embedder.embed_passages([c.contextual_text if use_header else c.text for c in chunks])
    col.add(
        ids=[c.id for c in chunks],
        documents=[c.text for c in chunks],
        embeddings=embeddings,
        metadatas=[{"source": c.source, "title": c.title, "section": c.section, "index": c.index} for c in chunks],
    )
    return len(chunks)
