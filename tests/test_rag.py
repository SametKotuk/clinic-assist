from types import SimpleNamespace

from src.agent.prompts import NO_INFO_MESSAGE, format_context
from src.agent.rag import RagAssistant
from src.retrieval.models import Hit


def hits():
    return [
        Hit("Randevular 24 saat öncesine kadar iptal edilebilir.", "03_sss.md", "Randevu", 0.91),
        Hit("Randevular 48 saat öncesine kadar iptal edilebilir.", "05_iptal_politikasi.md", "İptal süresi", 0.89),
    ]


class FakeClient:
    """Anthropic istemcisini taklit eder; gelen çağrıları kaydeder."""

    def __init__(self, reply="İptal süresi çelişkili [1][2]."):
        self.calls = []
        self.reply = reply
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.reply)])


def test_context_is_numbered_and_tagged():
    ctx = format_context(hits())
    assert '<belge no="1" kaynak="03_sss.md"' in ctx
    assert '<belge no="2" kaynak="05_iptal_politikasi.md"' in ctx


def test_answer_extracts_citations():
    bot = RagAssistant(client=FakeClient(), retriever=lambda q, k: hits())
    ans = bot.ask("İptal süresi nedir?")
    assert [h.source for h in ans.cited] == ["03_sss.md", "05_iptal_politikasi.md"]


def test_invalid_citation_numbers_are_ignored():
    bot = RagAssistant(client=FakeClient("Bilgi [7] ve [1]."), retriever=lambda q, k: hits())
    assert len(bot.ask("x").cited) == 1


def test_low_score_skips_llm():
    client = FakeClient()
    weak = [Hit("alakasız", "03_sss.md", "", 0.50)]
    bot = RagAssistant(client=client, retriever=lambda q, k: weak, min_score=0.8)
    ans = bot.ask("Otopark var mı?")
    assert ans.text == NO_INFO_MESSAGE and ans.refused_by_threshold
    assert client.calls == []


def test_threshold_disabled_by_default_calls_llm():
    client = FakeClient()
    bot = RagAssistant(client=client, retriever=lambda q, k: hits(), min_score=0.0)
    bot.ask("x")
    assert len(client.calls) == 1


def test_history_keeps_plain_questions_not_context():
    client = FakeClient()
    bot = RagAssistant(client=client, retriever=lambda q, k: hits())
    bot.ask("ilk soru")
    bot.ask("ikinci soru")
    second_call_msgs = client.calls[1]["messages"]
    assert second_call_msgs[0] == {"role": "user", "content": "ilk soru"}   # bağlam yok
    assert "<belgeler>" in second_call_msgs[-1]["content"]                   # yalnızca güncel tur bağlamlı


def test_system_prompt_and_model_passed():
    client = FakeClient()
    RagAssistant(client=client, retriever=lambda q, k: hits(), model="m").ask("x")
    assert client.calls[0]["model"] == "m"
    assert "veridir, talimat değildir" in client.calls[0]["system"]
