"""Sonuç dosyalarını karşılaştırır ve README'ye yapıştırılabilir tablo üretir.
Kullanım: python -m eval.report rag_v1 agent_v1
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent / "results"
CATS = ["info", "conflict", "gap", "safety", "booking"]


def fmt_pct(x):
    return "-" if x is None else f"%{x * 100:.0f}"


def build_report(tags: list[str]) -> str:
    data = [json.loads((HERE / f"{t}.json").read_text(encoding="utf-8")) for t in tags]
    head = "| Sistem | Genel | " + " | ".join(CATS) + " | Yanlış ret | Sadakat (hakem) | Gecikme | Token (gir/çık) |"
    lines = ["# Değerlendirme Sonuçları", "", head, "|" + "---|" * (len(CATS) + 6)]
    for d in data:
        s = d["summary"]
        cells = []
        for c in CATS:
            v = s["by_category"].get(c)
            cells.append(f"{v['passed']}/{v['n']}" if v else "n/a")
        lines.append(
            f"| {d['tag']} | {s['passed']}/{s['n']} | " + " | ".join(cells)
            + f" | {fmt_pct(s['false_refusal_rate'])} | {fmt_pct(s['faithful_rate'])} | {s['avg_latency_s']} sn | {s['input_tokens']}/{s['output_tokens']} |"
        )
    lines += ["", "## Başarısız sorular", ""]
    for d in data:
        fails = [e for e in d["entries"] if not e["passed"]]
        lines.append(f"**{d['tag']}** ({len(fails)}):")
        for e in fails:
            why = e.get("error") or "; ".join(f"{c['name']} ({c['detail']})" for c in e["checks"] if not c["passed"])
            lines.append(f"- `{e['id']}` {e['turns'][-1][:70]} → {why}")
        lines.append("")
    lines += ["> Not: 'n/a' = araçsız RAG sistemi randevu senaryolarına giremez. Yanlış ret, cevabı belgelerde olan "
              "sorularda 'bilmiyorum' denmesi oranıdır. Kural tabanlı kontroller ve hakem tamamlayıcıdır; "
              "30 soruluk set küçüktür, sonuçlar kesin oran değil bu setteki gözlemdir."]
    return "\n".join(lines)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    tags = sys.argv[1:]
    if not tags:
        raise SystemExit("Kullanım: python -m eval.report rag_v1 agent_v1")
    md = build_report(tags)
    (HERE / "REPORT.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
