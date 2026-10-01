"""Chunking deneyleri: aynı sorularla farklı parçalama stratejilerini karşılaştırır.
Kullanım: python -m eval.sweep [--keep]
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

from eval.retrieval_eval import evaluate, load_questions
from src.config import settings
from src.ingest.chunking import Chunk, chunk_directory
from src.ingest.embedder import Embedder
from src.ingest.indexer import build_index, get_collection
from src.retrieval.search import search

HERE = Path(__file__).parent


def naive_chunks(docs_dir: Path, size: int, overlap: int) -> list[Chunk]:
    """Yapıdan habersiz sabit boyutlu pencere (temel çizgi)."""
    chunks = []
    for path in sorted(docs_dir.glob("*.md")):
        text, n = path.read_text(encoding="utf-8"), 0
        for i in range(0, len(text), size - overlap):
            piece = text[i : i + size].strip()
            if piece:
                chunks.append(Chunk(f"{path.stem}-{n:03d}", piece, path.name, "", "", n))
                n += 1
    return chunks


CONFIGS = [
    # (ad, üretici, başlık kullan)
    ("naive_500", lambda d: naive_chunks(d, 500, 100), False),
    ("struct_300", lambda d: chunk_directory(d, 300, 50), True),
    ("struct_600 (varsayılan)", lambda d: chunk_directory(d, 600, 100), True),
    ("struct_1000", lambda d: chunk_directory(d, 1000, 150), True),
    ("struct_600_başlıksız", lambda d: chunk_directory(d, 600, 100), False),
]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--keep", action="store_true", help="Deney koleksiyonlarını silme")
    args = p.parse_args()

    questions, embedder, rows = load_questions(), Embedder(), []
    for name, make, use_header in CONFIGS:
        col = "exp_" + "".join(ch if ch.isalnum() else "_" for ch in name)
        chunks = make(settings.docs_dir)
        build_index(chunks, embedder, collection=col, use_header=use_header)
        res = evaluate(lambda q, k, c=col: search(q, k, collection=c), questions)
        s, t = res["summary"], res["threshold"]
        rows.append({"config": name, "chunks": len(chunks), "avg_len": round(statistics.mean(len(c.text) for c in chunks)),
                     "hit@1": s["hit@1"], "hit@3": s["hit@3"], "recall@4": s["recall@4"], "mrr": s["mrr"],
                     "score_gap": round(t["answerable_min"] - t["gap_max"], 3)})
        print(f"tamam: {name}")
        if not args.keep:
            import chromadb
            chromadb.PersistentClient(path=str(settings.chroma_path)).delete_collection(col)

    lines = ["| Yapılandırma | Chunk | Ort. uzunluk | Hit@1 | Hit@3 | Recall@4 | MRR | Skor farkı* |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['config']} | {r['chunks']} | {r['avg_len']} | {r['hit@1']:.2f} | {r['hit@3']:.2f} | "
                     f"{r['recall@4']:.2f} | {r['mrr']:.2f} | {r['score_gap']:+.3f} |")
    lines += ["", "*Skor farkı = cevaplanabilir soruların en düşük üst skoru − boşluk sorularının en yüksek üst skoru. "
              "Pozitifse skor eşiğiyle 'bilmiyorum' ayrımı mümkündür."]
    md = "\n".join(lines)
    print("\n" + md)
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "sweep.md").write_text(md, encoding="utf-8")
    (HERE / "results" / "sweep.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
