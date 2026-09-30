"""RAG çekirdeği: ara -> bağlamı hazırla -> Claude -> kaynaklı yanıt."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from src.agent.prompts import NO_INFO_MESSAGE, SYSTEM_PROMPT, build_user_message
from src.config import settings
from src.retrieval.models import Hit

Retriever = Callable[[str, int], list[Hit]]


@dataclass
class RagAnswer:
    text: str
    retrieved: list[Hit] = field(default_factory=list)   # aranan tüm parçalar
    cited: list[Hit] = field(default_factory=list)       # yanıtta [n] ile anılanlar
    refused_by_threshold: bool = False                    # skor eşiği yüzünden LLM çağrılmadı
    input_tokens: int = 0
    output_tokens: int = 0


def _default_retriever(query: str, k: int) -> list[Hit]:
    from src.retrieval.search import search  # ağır bağımlılıkları geç yükle

    return search(query, k)


class RagAssistant:
    def __init__(
        self,
        client=None,
        retriever: Retriever | None = None,
        model: str | None = None,
        top_k: int | None = None,
        min_score: float | None = None,
    ):
        self._client = client
        self.retriever = retriever or _default_retriever
        self.model = model or settings.claude_model
        self.top_k = top_k if top_k is not None else settings.top_k
        self.min_score = min_score if min_score is not None else settings.min_score
        self.history: list[dict] = []   # yalnızca (soru, yanıt) çiftleri; bağlam saklanmaz

    @property
    def client(self):
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic()  # ANTHROPIC_API_KEY ortamdan okunur
        return self._client

    def reset(self) -> None:
        self.history.clear()

    def ask(self, question: str) -> RagAnswer:
        question = question.strip()
        hits = self.retriever(question, self.top_k)

        # Eşik kapısı: en iyi sonuç bile zayıfsa LLM'e hiç gitme.
        if self.min_score > 0 and (not hits or max(h.score for h in hits) < self.min_score):
            return RagAnswer(NO_INFO_MESSAGE, retrieved=hits, refused_by_threshold=True)

        messages = self.history + [{"role": "user", "content": build_user_message(question, hits)}]
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1000,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        text = "".join(b.text for b in response.content if getattr(b, "type", "") == "text").strip()

        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "assistant", "content": text})
        usage = getattr(response, "usage", None)
        return RagAnswer(
            text, retrieved=hits, cited=self._cited(text, hits),
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )

    @staticmethod
    def _cited(text: str, hits: list[Hit]) -> list[Hit]:
        numbers = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text)})
        return [hits[n - 1] for n in numbers if 1 <= n <= len(hits)]
