"""Metinleri embedding'e çevirip JSON dosyasına (Pure Python) kaydeder."""
from __future__ import annotations

import json
from pathlib import Path

from src.config import settings
from src.indexer import Chunk
from src.ingest.embedder import Embedder

DB_FILE = Path(settings.chroma_path) / "local_index.json"

def build_index(chunks: list[Chunk], embedder: Embedder, reset: bool = True,
                collection: str | None = None, use_header: bool = True) -> int:
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    embeddings = embedder.embed_passages([c.contextual_text if use_header else c.text for c in chunks])
    data = []
    for c, emb in zip(chunks, embeddings):
        data.append({
            "id": c.id, "text": c.text, "embedding": emb,
            "source": c.source, "title": c.title, "section": c.section, "index": c.index
        })
    DB_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return len(chunks)