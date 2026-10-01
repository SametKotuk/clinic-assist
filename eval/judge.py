"""LLM hakem: cevabın kaynaklara sadakatini değerlendirir."""
from __future__ import annotations

import json
import re

JUDGE_PROMPT = """Sen titiz bir değerlendiricisin. Bir diş kliniği asistanının cevabını, asistana \
verilen kaynaklara göre değerlendir.

<kaynaklar>
{contexts}
</kaynaklar>

<soru>{question}</soru>

<cevap>{answer}</cevap>

Belirle:
- faithful: Cevaptaki klinik-spesifik tüm olgular (fiyat, süre, saat, politika, hekim bilgisi) \
kaynaklarda destekleniyor mu? Kaynakta olmayan bir olgu uydurulmuşsa false.
- properly_declined: Sorunun cevabı kaynaklarda YOKSA asistan bunu dürüstçe söyledi mi? \
Cevap kaynaklarda varsa null yaz.
- notes: En fazla iki cümlelik gerekçe.

Yalnızca şu JSON'u döndür, başka hiçbir şey yazma:
{{"faithful": true, "properly_declined": null, "notes": "..."}}"""


def parse_verdict(raw: str) -> dict:
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return {"faithful": None, "properly_declined": None, "notes": f"ayrıştırılamadı: {raw[:80]}"}
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"faithful": None, "properly_declined": None, "notes": f"geçersiz JSON: {raw[:80]}"}
    return {
        "faithful": data.get("faithful"),
        "properly_declined": data.get("properly_declined"),
        "notes": str(data.get("notes", ""))[:300],
    }


def judge(client, model: str, question: str, answer: str, contexts: list[str]) -> dict:
    ctx = "\n---\n".join(contexts) if contexts else "(kaynak yok)"
    prompt = JUDGE_PROMPT.format(contexts=ctx, question=question, answer=answer)
    
    from google.genai import types
    
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=400,
            temperature=0.0
        )
    )
    raw = resp.text if resp.text else ""
    return parse_verdict(raw)