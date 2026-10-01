"""Retrieval değerlendirmesi.
Kullanım: python -m eval.retrieval_eval --tag baseline [--k 4]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from eval.metrics import first_rank, recall_at_k, suggest_threshold, summarize

HERE = Path(__file__).parent
KS = (1, 3, 4)


def load_questions() -> list[dict]:
    return json.loads((HERE / "retrieval_questions.json").read_text(encoding="utf-8"))


def evaluate(search_fn, questions: list[dict], max_k: int = 4, verbose: bool = False) -> dict:
    """search_fn(query, k) -> list[Hit]. Özet, eşik analizi ve ayrıntıyı döndürür."""
    rows, answerable_top, gap_top, detail = [], [], [], []
    for item in questions:
        hits = search_fn(item["q"], max(max_k, max(KS)))
        sources = [h.source for h in hits]
        top = hits[0].score
        rec = {"id": item["id"], "q": item["q"], "type": item["type"], "top_score": round(top, 3),
               "ranked": [(h.source, round(h.score, 3)) for h in hits]}
        if item["type"] == "gap":
            gap_top.append(top)
            if verbose:
                print(f"[{item['id']}] GAP   top={top:.3f}  {item['q']}")
        else:
            rank = first_rank(sources, item["expected"])
            recall = {k: recall_at_k(sources, item["expected"], k) for k in KS}
            answerable_top.append(top)
            rows.append({"rank": rank, "recall": recall})
            rec.update(rank=rank, recall=recall)
            if verbose:
                print(f"[{item['id']}] {'OK  ' if rank else 'MISS'} rank={rank} top={top:.3f}  {item['q']}")
        detail.append(rec)
    return {"summary": summarize(rows, KS), "threshold": suggest_threshold(answerable_top, gap_top), "detail": detail}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    from src.retrieval.search import search

    p = argparse.ArgumentParser()
    p.add_argument("--tag", default="baseline")
    p.add_argument("--k", type=int, default=4)
    args = p.parse_args()

    res = evaluate(search, load_questions(), args.k, verbose=True)
    summary, threshold = res["summary"], res["threshold"]
    print("\n=== ÖZET ===")
    for k, v in summary.items():
        print(f"{k:10s} {v:.3f}" if isinstance(v, float) else f"{k:10s} {v}")
    print(f"\nCevaplanabilir soruların EN DÜŞÜK üst skoru: {threshold['answerable_min']:.3f}")
    print(f"Boşluk sorularının EN YÜKSEK üst skoru:      {threshold['gap_max']:.3f}")
    if threshold["separable"]:
        print(f"Skorlar ayrışıyor. Önerilen MIN_SCORE ≈ {threshold['suggested']}")
    else:
        print("Skorlar ÜST ÜSTE biniyor: tek başına skor eşiği yeterli değil,")
        print("boşluk davranışını sistem promptu ve LLM'e bırakmak gerekecek.")
    out = HERE / "results" / f"retrieval_{args.tag}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nKaydedildi: {out}")


if __name__ == "__main__":
    main()
