"""multilingual-e5 tabanlı embedding sarmalayıcısı.

E5 modelleri, doküman metninde "passage: " ve sorguda "query: " öneki bekler.
Önek unutulursa arama kalitesi belirgin şekilde düşer.
"""
from __future__ import annotations

from src.config import settings


class Embedder:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model
        self._model = None

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer  # geç yükleme: import hızlı kalsın

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
        return vecs.tolist()

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return self._encode([f"passage: {t}" for t in texts])

    def embed_query(self, query: str) -> list[float]:
        return self._encode([f"query: {query}"])[0]
