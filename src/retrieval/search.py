"""Vektör araması (Pure Python, ChromaDB kullanılmaz)."""
from __future__ import annotations

import json
import math
from pathlib import Path

from src.config import settings
from src.ingest.embedder import Embedder
from src.retrieval.models import Hit

DB_FILE = Path(settings.chroma_path) / "local_index.json"
_embedder: Embedder | None = None
_docs: list[dict] | None = None

def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0: return 0.0
    return dot / (mag1 * mag2)

def search(query: str, k: int = 4, collection: str | None = None) -> list[Hit]:
    global _embedder, _docs
    
    # 1. Eğer indeks dosyası yoksa otomatik olarak oluştur (İlk çalıştırmada devreye girer)
    if not DB_FILE.exists():
        from src.ingest.indexer import build_index
        from src.ingest.chunking import chunk_directory
        _embedder = _embedder or Embedder()
        print("\n[BİLGİ] Klinik belgeleri indeksleniyor, lütfen birkaç saniye bekleyin...\n")
        build_index(chunk_directory(settings.docs_dir), _embedder)

    # 2. Veritabanını belleğe al
    if _docs is None:
        _docs = json.loads(DB_FILE.read_text(encoding="utf-8"))

    # 3. Sorguyu vektöre çevir
    _embedder = _embedder or Embedder()
    q_emb = _embedder.embed_query(query)

    # 4. Kosinüs benzerliği ile skorla
    scored = []
    for doc in _docs:
        score = cosine_similarity(q_emb, doc["embedding"])
        scored.append((score, doc))

    # 5. En yüksek skorlu k sonucu döndür
    scored.sort(key=lambda x: x[0], reverse=True)
    hits = []
    for score, doc in scored[:k]:
        hits.append(Hit(doc["text"], doc["source"], doc["section"], score))
        
    return hits