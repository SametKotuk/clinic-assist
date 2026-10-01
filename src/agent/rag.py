"""RAG çekirdeği: ara -> bağlamı hazırla -> Gemini -> kaynaklı yanıt."""
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
    retrieved: list[Hit] = field(default_factory=list)
    cited: list[Hit] = field(default_factory=list)
    refused_by_threshold: bool = False
    input_tokens: int = 0
    output_tokens: int = 0


def _default_retriever(query: str, k: int) -> list[Hit]:
    from src.retrieval.search import search
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
        # Varsayılan modeli Gemini yapıyoruz
        self.model = model or "gemini-3.5-flash-lite"
        self.top_k = top_k if top_k is not None else settings.top_k
        self.min_score = min_score if min_score is not None else settings.min_score
        self.history: list[dict] = []

    @property
    def client(self):
        if self._client is None:
            from google import genai
            self._client = genai.Client()  # GEMINI_API_KEY ortamdan okunur
        return self._client

    def reset(self) -> None:
        self.history.clear()

    def ask(self, question: str) -> RagAnswer:
        question = question.strip()
        hits = self.retriever(question, self.top_k)

        if self.min_score > 0 and (not hits or max(h.score for h in hits) < self.min_score):
            return RagAnswer(NO_INFO_MESSAGE, retrieved=hits, refused_by_threshold=True)

        from google.genai import types

        # Gemini formatına uygun mesaj geçmişini hazırla
        formatted_contents = []
        for msg in self.history:
            formatted_contents.append(
                types.Content(role=msg["role"], parts=[types.Part.from_text(text=msg["content"])])
            )
        
        # Yeni soruyu bağlam ile birlikte ekle
        formatted_contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=build_user_message(question, hits))])
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=formatted_contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=1000,
                temperature=0.0
            )
        )
        
        text = response.text.strip() if response.text else ""

        self.history.append({"role": "user", "content": question})
        self.history.append({"role": "model", "content": text}) # Gemini'de asistan rolü 'model' olarak geçer

        in_tokens = response.usage_metadata.prompt_token_count if getattr(response, "usage_metadata", None) else 0
        out_tokens = response.usage_metadata.candidates_token_count if getattr(response, "usage_metadata", None) else 0

        return RagAnswer(
            text, retrieved=hits, cited=self._cited(text, hits),
            input_tokens=in_tokens,
            output_tokens=out_tokens,
        )

    @staticmethod
    def _cited(text: str, hits: list[Hit]) -> list[Hit]:
        numbers = sorted({int(n) for n in re.findall(r"\[(\d+)\]", text)})
        return [hits[n - 1] for n in numbers if 1 <= n <= len(hits)]