"""Terminalde sohbet.
Kullanım: python -m src.agent.cli [--debug] [--rag-only]
"""
from __future__ import annotations

import argparse
import sys


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser()
    p.add_argument("--debug", action="store_true", help="Araç çağrılarını göster")
    p.add_argument("--rag-only", action="store_true", help="Gün 3'teki araçsız RAG asistanı (karşılaştırma için)")
    args = p.parse_args()

    if args.rag_only:
        from src.agent.rag import RagAssistant
        bot = RagAssistant()
    else:
        from src.agent.agent import ClinicAgent
        bot = ClinicAgent()

    print("ClinicAssist (çıkmak için q, sıfırlamak için /reset)\n")
    while True:
        try:
            q = input("Sen: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"q", "quit", "exit"}:
            break
        if q == "/reset":
            bot.reset()
            print("(konuşma sıfırlandı)\n")
            continue
        try:
            ans = bot.ask(q) if args.rag_only else bot.chat(q)
        except Exception as e:
            print(f"[hata] {type(e).__name__}: {e}\n")
            continue
        print(f"\nAsistan: {ans.text}\n")
        if ans.cited:
            print("Kaynaklar: " + "; ".join(f"{h.source} > {h.section or '-'}" for h in ans.cited))
        if args.debug and not args.rag_only:
            for c in ans.tool_calls:
                flag = " [HATA]" if c.is_error else ""
                print(f"  ⚙ {c.name}({c.input}){flag}")
        print()


if __name__ == "__main__":
    main()
