"""Retrieval metrikleri (LLM kullanmaz, deterministiktir)."""
from __future__ import annotations


def first_rank(ranked_sources: list[str], expected: list[str]) -> int | None:
    """Beklenen kaynaklardan ilkinin 1 tabanlı sırası; yoksa None."""
    for i, s in enumerate(ranked_sources, 1):
        if s in expected:
            return i
    return None


def recall_at_k(ranked_sources: list[str], expected: list[str], k: int) -> float:
    """Beklenen kaynakların kaçı ilk k sonuçta?"""
    if not expected:
        return 1.0
    found = set(ranked_sources[:k]) & set(expected)
    return len(found) / len(set(expected))


def summarize(rows: list[dict], ks: tuple[int, ...] = (1, 3, 4)) -> dict:
    """rows: her biri {'ranks': int|None, 'recall': {k: float}} içeren cevaplanabilir sorular."""
    n = len(rows)
    out = {"n": n}
    for k in ks:
        out[f"hit@{k}"] = sum(1 for r in rows if r["rank"] is not None and r["rank"] <= k) / n if n else 0.0
        out[f"recall@{k}"] = sum(r["recall"][k] for r in rows) / n if n else 0.0
    out["mrr"] = sum(1 / r["rank"] for r in rows if r["rank"]) / n if n else 0.0
    return out


def suggest_threshold(answerable_top: list[float], gap_top: list[float]) -> dict:
    """Cevaplanabilir sorulardaki en düşük ve boşluk sorularındaki en yüksek üst skoru karşılaştırır."""
    lo, hi = min(answerable_top), max(gap_top)
    return {
        "answerable_min": lo,
        "gap_max": hi,
        "separable": lo > hi,
        "suggested": round((lo + hi) / 2, 3) if lo > hi else None,
    }
