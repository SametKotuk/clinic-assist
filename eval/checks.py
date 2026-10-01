"""Kural tabanlı kontroller: deterministik, tekrarlanabilir, LLM kullanmaz.

Metin karşılaştırmaları Türkçe karakterlerden arındırılmış küçük harfli biçim üzerinde yapılır,
böylece "İptal"/"iptal" ve "şişlik"/"sislik" aynı sayılır.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_TR = str.maketrans({
    "İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c",
    "–": "-", "—": "-", "’": "'", "\u00a0": " ",
})

# "Bilmiyorum" tespiti yaklaşıktır; hakem ve elle inceleme ile tamamlanır.
UNKNOWN_PATTERNS = [
    r"bilgi\w*\s+(bulunmuyor|bulunamad|yok\b|yer almiyor|mevcut degil)",
    r"bilgim\s+yok", r"bilmiyorum", r"(net|kesin)\s+(bir\s+)?bilgi",
    r"(belgelerde|elimde|kaynaklarda|mevcut belgelerde)\b.{0,60}(yok\b|yer almiyor|bulunmuyor|bulunamad)",
    r"(bilgi|bilgiye)\s+(sahip degilim|erisemiyorum)",
]
CONFLICT_MARKERS = ["celis", "tutarsiz", "farkli", "teyit", "dogrula", "netlestir", "uyusm", "emin degil"]
ALLOWED_PHONES = {"02165550123", "2165550123", "902165550123"}


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").translate(_TR).lower()).strip()


def looks_unknown(text: str) -> bool:
    t = norm(text)
    return any(re.search(p, t) for p in UNKNOWN_PATTERNS)


def find_times(text: str) -> set[str]:
    return {f"{int(h):02d}:{m}" for h, m in re.findall(r"(?<!\d)([01]?\d|2[0-3])[:.]([0-5]\d)(?!\d)", norm(text))}


def foreign_phone_numbers(text: str) -> list[str]:
    found = []
    for m in re.findall(r"\+?\d[\d\s\-()]{8,}\d", text or ""):
        digits = re.sub(r"\D", "", m)
        if len(digits) >= 10 and digits not in ALLOWED_PHONES:
            found.append(digits)
    return found


@dataclass
class Result:
    """Bir sorunun (tüm turların) normalleştirilmiş çıktısı."""
    text: str                                        # son turdaki yanıt
    tool_calls: list[dict] = field(default_factory=list)   # {name, input, is_error}
    cited_sources: list[str] = field(default_factory=list)
    has_tools: bool = True                           # RAG-only sistemde araç kontrolleri atlanır


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


def run_checks(spec: dict, res: Result, appointments: list[dict]) -> list[CheckResult]:
    out: list[CheckResult] = []
    add = lambda name, ok, detail="": out.append(CheckResult(name, bool(ok), detail))
    t = norm(res.text)
    called = {c["name"] for c in res.tool_calls}

    for i, group in enumerate(spec.get("include", [])):
        add(f"include[{i}]", any(norm(a) in t for a in group), f"beklenen: {' | '.join(group)}")
    for s in spec.get("exclude", []):
        add(f"exclude:{s}", norm(s) not in t)
    for p in spec.get("exclude_regex", []):
        add(f"exclude_regex:{p}", not re.search(p, t))

    if "unknown" in spec:
        got = looks_unknown(res.text)
        add("unknown" if spec["unknown"] else "not_unknown", got == spec["unknown"],
            f"'bilmiyorum' algılandı={got}")
    if spec.get("conflict_markers"):
        add("conflict_marker", any(m in t for m in CONFLICT_MARKERS), "çelişkiyi belirten ifade aranıyor")

    cited = set(res.cited_sources)
    if "cite_all" in spec:
        missing = [s for s in spec["cite_all"] if s not in cited]
        add("cite_all", not missing, f"eksik kaynak: {missing}" if missing else "")
    if "cite_any" in spec:
        add("cite_any", bool(cited & set(spec["cite_any"])), f"atıf yapılanlar: {sorted(cited)}")

    if res.has_tools:
        if "tools_called" in spec:
            missing = [n for n in spec["tools_called"] if n not in called]
            add("tools_called", not missing, f"çağrılmayan: {missing}" if missing else "")
        if "tools_not_called" in spec:
            bad = [n for n in spec["tools_not_called"] if n in called]
            add("tools_not_called", not bad, f"çağrılan yasak araç: {bad}" if bad else "")
    if "db_count" in spec:
        add("db_count", len(appointments) == spec["db_count"], f"kayıt sayısı={len(appointments)}")
    if "db_has" in spec:
        w = spec["db_has"]
        ok = any(a["start_at"] == f"{w['date']} {w['time']}" and a["treatment_id"] == w["treatment"]
                 and norm(a["patient_name"]) == norm(w["name"]) for a in appointments)
        add("db_has", ok, "beklenen randevu veritabanında")
    if "alt_times" in spec:
        cfg = spec["alt_times"]
        alts = find_times(res.text) - {x for x in cfg.get("exclude", [])}
        add("alt_times", len(alts) >= cfg.get("min", 1), f"önerilen alternatif saatler: {sorted(alts)}")
    if spec.get("asks_question"):
        add("asks_question", "?" in res.text)
    if spec.get("no_foreign_phone"):
        bad = foreign_phone_numbers(res.text)
        add("no_foreign_phone", not bad, f"belgelerde olmayan numara: {bad}" if bad else "")
    return out
