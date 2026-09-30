"""Merkezi ayarlar. Değerler .env dosyasından veya ortam değişkenlerinden okunur."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    docs_dir: Path = ROOT / "data" / "docs"
    chroma_path: Path = ROOT / os.getenv("CHROMA_PATH", ".chroma")
    collection: str = "clinic_docs"
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "intfloat/multilingual-e5-small")
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "600"))      # karakter
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "100"))  # karakter


settings = Settings()
