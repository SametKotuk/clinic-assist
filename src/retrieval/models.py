from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Hit:
    text: str
    source: str
    section: str
    score: float  # kosinüs benzerliği (1 = birebir)
