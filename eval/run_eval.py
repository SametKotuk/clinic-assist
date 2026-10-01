"""Değerlendirme koşucusu.

Örnekler:
  python -m eval.run_eval --system agent --tag agent_v1 --judge
  python -m eval.run_eval --system rag   --tag rag_v1   --judge
  python -m eval.run_eval --system agent --category safety
  python -m eval.run_eval --system agent --only c01,b01 --repeat 3

Saat sabitlenir (29.09.2026 Salı 10:00), böylece "yarın" gibi ifadeler her koşuda aynı günü gösterir.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime
from pathlib import Path

from eval.checks import Result, looks_unknown, run_checks
from src.booking.service import BookingService
from src.booking.store import AppointmentStore

HERE = Path(__file__).parent
FIXED_NOW = datetime(2026, 9, 29, 10, 0)
CATEGORIES = ["info", "conflict", "gap", "safety", "booking"]


class AgentAdapter:
    has_tools = True

    def __init__(self, agent):
        self.agent = agent

    def turn(self, text: str) -> dict:
        r = self.agent.chat(text)
        return {"text": r.text, "in": r.input_tokens, "out": r.output_tokens,
                "tools": [{"name": c.name, "input": c.input, "is_error": c.is_error, "result": c.result} for c in r.tool_calls],
                "cited": [h.source for h in r.cited]}

    def contexts(self) -> list[str]:
        return [h.text for h in self.agent.tools.sources.values()]


class RagAdapter:
    has_tools = False

    def __init__(self, rag):
        self.rag, self._ctx = rag, []

    def turn(self, text: str) -> dict:
        r = self.rag.ask(text)
        self._ctx += [h.text for h in r.retrieved]
        return {"text": r.text, "in": r.input_tokens, "out": r.output_tokens, "tools": [],
                "cited": [h.source for h in r.cited]}

    def contexts(self) -> list[str]:
        return list(dict.fromkeys(self._ctx))


def make_bot(kind: str, booking: BookingService, min_score: float):
    if kind == "agent":
        from src.agent.agent import ClinicAgent
        return AgentAdapter(ClinicAgent(booking=booking, now_fn=lambda: FIXED_NOW))
    from src.agent.rag import RagAssistant
    return RagAdapter(RagAssistant(min_score=min_score))


def run_item(item: dict, bot_factory, judge_fn=None) -> dict:
    """Tek soruyu (tüm turlarıyla) çalıştırır. bot_factory(booking) -> adaptör."""
    store = AppointmentStore(":memory:")
    booking = BookingService(store, now_fn=lambda: FIXED_NOW)
    for s in item.get("seed", []):
        booking.book(s["date"], s["time"], s["treatment"], s["name"], s["phone"])

    turns = item.get("turns") or [item["q"]]
    entry = {"id": item["id"], "category": item["category"], "turns": turns}
    t0 = time.time()
    try:
        bot = bot_factory(booking)
        replies = [bot.turn(t) for t in turns]
    except Exception as e:  # tek soru hatası tüm koşuyu düşürmesin
        entry.update(error=f"{type(e).__name__}: {e}", passed=False, checks=[], answer="", latency_s=round(time.time() - t0, 2))
        return entry

    last = replies[-1]
    all_tools = [{"name": c["name"], "input": c["input"], "is_error": c["is_error"]} for r in replies for c in r["tools"]]
    result = Result(last["text"], all_tools, sorted({s for r in replies for s in r["cited"]}), bot.has_tools)
    checks = run_checks(item.get("checks", {}), result, store.all_confirmed())

    entry.update(
        answer=last["text"], transcript=[r["text"] for r in replies], tool_calls=all_tools,
        cited_sources=result.cited_sources, checks=[c.__dict__ for c in checks],
        passed=all(c.passed for c in checks), looks_unknown=looks_unknown(last["text"]),
        latency_s=round(time.time() - t0, 2),
        input_tokens=sum(r["in"] for r in replies), output_tokens=sum(r["out"] for r in replies),
        appointments=len(store.all_confirmed()),
    )
    if judge_fn and item["category"] != "booking":
        entry["judge"] = judge_fn(item.get("q", turns[-1]), last["text"], bot.contexts())
    return entry


def summarize(entries: list[dict]) -> dict:
    by_cat = {}
    for c in CATEGORIES:
        rows = [e for e in entries if e["category"] == c]
        if rows:
            by_cat[c] = {"n": len(rows), "passed": sum(e["passed"] for e in rows)}
    n = len(entries)
    answerable = [e for e in entries if e["category"] in ("info", "conflict") and e.get("answer")]
    judged = [e["judge"] for e in entries if e.get("judge") and e["judge"]["faithful"] is not None]
    return {
        "n": n, "passed": sum(e["passed"] for e in entries), "by_category": by_cat,
        "false_refusal_rate": (sum(e["looks_unknown"] for e in answerable) / len(answerable)) if answerable else None,
        "faithful_rate": (sum(bool(j["faithful"]) for j in judged) / len(judged)) if judged else None,
        "avg_latency_s": round(sum(e["latency_s"] for e in entries) / n, 2) if n else None,
        "input_tokens": sum(e.get("input_tokens", 0) for e in entries),
        "output_tokens": sum(e.get("output_tokens", 0) for e in entries),
        "errors": sum(1 for e in entries if e.get("error")),
    }


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--system", choices=["agent", "rag"], default="agent")
    p.add_argument("--tag", default=None)
    p.add_argument("--judge", action="store_true", help="LLM hakemi çalıştır")
    p.add_argument("--repeat", type=int, default=1, help="Her soruyu N kez çalıştır (LLM değişkenliği için)")
    p.add_argument("--category", choices=CATEGORIES)
    p.add_argument("--only", help="Virgülle ayrılmış soru id'leri")
    p.add_argument("--min-score", type=float, default=0.0, help="RAG için skor eşiği")
    p.add_argument("--review-sample", type=int, default=0, help="Elle doğrulama için N cevap örnekle")
    args = p.parse_args()
    tag = args.tag or args.system

    items = json.loads((HERE / "dataset.json").read_text(encoding="utf-8"))
    if args.system == "rag":
        items = [i for i in items if i["category"] != "booking"]  # araçsız sistem randevu alamaz
    if args.category:
        items = [i for i in items if i["category"] == args.category]
    if args.only:
        wanted = set(args.only.split(","))
        items = [i for i in items if i["id"] in wanted]

    judge_fn = None
    if args.judge:
        from google import genai
        from eval.judge import judge
        jc = genai.Client()
        judge_fn = lambda q, a, ctx: judge(jc, "gemini-3.5-flash-lite", q, a, ctx)

    entries = []
    for item in items:
        for rep in range(args.repeat):
            e = run_item(item, lambda b: make_bot(args.system, b, args.min_score), judge_fn)
            e["run"] = rep + 1
            entries.append(e)
            status = "PASS" if e["passed"] else "FAIL"
            failed = [c["name"] for c in e["checks"] if not c["passed"]]
            extra = f" | başarısız: {failed}" if failed else ""
            extra += f" | HATA: {e['error']}" if e.get("error") else ""
            print(f"[{item['id']}#{rep + 1}] {status} ({e['latency_s']}s){extra}")

    s = summarize(entries)
    print("\n=== ÖZET ===")
    print(f"Genel: {s['passed']}/{s['n']}")
    for c, v in s["by_category"].items():
        print(f"  {c:9s} {v['passed']}/{v['n']}")
    for k in ("false_refusal_rate", "faithful_rate", "avg_latency_s", "input_tokens", "output_tokens", "errors"):
        print(f"{k}: {s[k]}")

    out = HERE / "results" / f"{tag}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"tag": tag, "system": args.system, "min_score": args.min_score,
                               "timestamp": datetime.now().isoformat(timespec="seconds"),
                               "summary": s, "entries": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nKaydedildi: {out}")

    if args.review_sample:
        rnd = random.Random(42)
        pool = [e for e in entries if e.get("answer")]
        sample = rnd.sample(pool, min(args.review_sample, len(pool)))
        lines = ["# Elle doğrulama örneklemi", "", "Her cevabı kaynaklarla karşılaştırıp 'İnsan kararı' sütununu doldur (doğru/yanlış).", "",
                 "| Soru | Cevap | Otomatik | Hakem | İnsan kararı |", "|---|---|---|---|---|"]
        for e in sample:
            q = e["turns"][-1].replace("|", "/")
            a = e["answer"].replace("\n", " ").replace("|", "/")[:400]
            j = e.get("judge", {}).get("faithful", "-")
            lines.append(f"| {e['id']}: {q} | {a} | {'geçti' if e['passed'] else 'kaldı'} | {j} |  |")
        rv = HERE / "results" / f"{tag}_review.md"
        rv.write_text("\n".join(lines), encoding="utf-8")
        print(f"Elle inceleme dosyası: {rv}")


if __name__ == "__main__":
    main()
