import json
from datetime import datetime
from types import SimpleNamespace

import pytest

from src.agent.agent import STEP_LIMIT_MESSAGE, TOO_LONG_MESSAGE, ClinicAgent
from src.booking.service import BookingService
from src.booking.store import AppointmentStore
from src.retrieval.models import Hit

NOW = datetime(2026, 9, 29, 10, 0)


def text(t):
    return SimpleNamespace(type="text", text=t)


def tool(id_, name, **inp):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=inp)


def resp(stop, *blocks):
    return SimpleNamespace(stop_reason=stop, content=list(blocks))


class ScriptedClient:
    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []
        self.messages = self

    def create(self, **kw):
        self.calls.append(json.loads(json.dumps(kw["messages"])))  # o anki kopya
        if not self.responses:
            raise RuntimeError("script bitti")
        return self.responses.pop(0)


def make_agent(*responses, retriever=None):
    booking = BookingService(AppointmentStore(":memory:"), now_fn=lambda: NOW)
    retriever = retriever or (lambda q, k: [
        Hit("İptal 48 saat öncesine kadar.", "05_iptal_politikasi.md", "İptal süresi", 0.9)])
    return ClinicAgent(client=ScriptedClient(*responses), booking=booking, retriever=retriever, now_fn=lambda: NOW)


def test_tool_loop_returns_final_text_with_citation():
    agent = make_agent(
        resp("tool_use", tool("t1", "retrieve_docs", query="iptal süresi")),
        resp("end_turn", text("48 saat [1].")),
    )
    r = agent.chat("İptal süresi ne kadar?")
    assert r.text == "48 saat [1]." and r.steps == 2
    assert r.tool_calls[0].name == "retrieve_docs"
    assert r.cited[0].source == "05_iptal_politikasi.md"
    # 2. çağrıya tool_result gitmiş olmalı
    last = agent.client.calls[1][-1]
    assert last["role"] == "user" and last["content"][0]["type"] == "tool_result"
    assert "<belge no=\"1\"" in last["content"][0]["content"]


def test_booking_requires_confirmation_flag():
    args = dict(date="2026-09-30", time="10:00", treatment="dolgu",
                patient_name="Ayşe Yılmaz", phone="05321234567", patient_confirmed=False)
    agent = make_agent(resp("tool_use", tool("t1", "book_appointment", **args)), resp("end_turn", text("Onay ister misiniz?")))
    r = agent.chat("Yarın 10:00 dolgu yaz")
    assert r.tool_calls[0].is_error and "not_confirmed" in r.tool_calls[0].result


def test_confirmed_booking_succeeds_and_blocks_duplicate():
    args = dict(date="2026-09-30", time="10:00", treatment="dolgu",
                patient_name="Ayşe Yılmaz", phone="05321234567", patient_confirmed=True)
    agent = make_agent(
        resp("tool_use", tool("t1", "book_appointment", **args)), resp("end_turn", text("Tamam.")),
        resp("tool_use", tool("t2", "book_appointment", **args)), resp("end_turn", text("Dolu.")),
    )
    ok = agent.chat("evet onaylıyorum")
    assert not ok.tool_calls[0].is_error and '"confirmed"' in ok.tool_calls[0].result
    dup = agent.chat("bir daha")
    assert dup.tool_calls[0].is_error and "slot_unavailable" in dup.tool_calls[0].result


def test_bad_tool_arguments_do_not_crash():
    agent = make_agent(resp("tool_use", tool("t1", "check_slots", date="2026-09-30")), resp("end_turn", text("ok")))
    r = agent.chat("müsait mi")
    assert r.tool_calls[0].is_error and "bad_arguments" in r.tool_calls[0].result


def test_unknown_tool_is_error():
    agent = make_agent(resp("tool_use", tool("t1", "delete_all")), resp("end_turn", text("ok")))
    assert agent.chat("x").tool_calls[0].is_error


def test_step_limit():
    loop = [resp("tool_use", tool(f"t{i}", "retrieve_docs", query="x")) for i in range(10)]
    agent = make_agent(*loop)
    agent.max_steps = 3
    r = agent.chat("x")
    assert r.text == STEP_LIMIT_MESSAGE and len(agent.client.calls) == 3
    assert agent.messages[-1]["role"] == "assistant"   # rol sırası bozulmadı


def test_input_guards_skip_api():
    agent = make_agent()
    assert agent.chat("a" * 2000).text == TOO_LONG_MESSAGE
    assert agent.chat("   ").text
    assert agent.client.calls == []


def test_api_error_rolls_back_history():
    agent = make_agent()  # script boş: create RuntimeError fırlatır
    with pytest.raises(RuntimeError):
        agent.chat("merhaba")
    assert agent.messages == []


def test_source_numbers_stay_stable_across_calls():
    hits = {"a": [Hit("A", "a.md", "", 0.9)], "b": [Hit("B", "b.md", "", 0.8)]}
    agent = make_agent(
        resp("tool_use", tool("t1", "retrieve_docs", query="a")),
        resp("tool_use", tool("t2", "retrieve_docs", query="b")),
        resp("tool_use", tool("t3", "retrieve_docs", query="a")),   # aynı parça: numara değişmemeli
        resp("end_turn", text("A [1], B [2].")),
        retriever=lambda q, k: hits[q],
    )
    r = agent.chat("x")
    assert [h.source for h in r.cited] == ["a.md", "b.md"]
    assert len(agent.tools.sources) == 2


def test_system_prompt_contains_current_date():
    from src.agent.agent_prompt import build_agent_prompt
    p = build_agent_prompt(NOW)
    assert "Salı" in p and "29.09.2026" in p
