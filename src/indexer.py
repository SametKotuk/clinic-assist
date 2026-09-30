"""Markdown'a duyarlı parçalama (chunking).

Strateji:
1. Dokümanı başlıklara (#, ##, ###) göre bölümlere ayır. Her bölüm doğal bir anlam birimidir.
2. Bölüm içindeki blokları (paragraf / tablo) chunk_size sınırına kadar birleştir.
3. Sınırı aşan tabloyu satır satır böl ve başlık satırını her parçada tekrarla.
4. Sınırı aşan paragrafı cümle sınırlarından böl; parçalar arasında overlap bırak.
5. Her chunk'a "Doküman > Bölüm" bağlam başlığı ekle (embedding kalitesini artırır).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Chunk:
    id: str
    text: str      # gövde metni (kullanıcıya/LLM'e gösterilen)
    source: str    # dosya adı
    title: str     # doküman başlığı (h1)
    section: str   # bölüm yolu (h2 > h3)
    index: int

    @property
    def contextual_text(self) -> str:
        """Embedding'e giren metin: bağlam başlığı + gövde."""
        header = self.title if not self.section else f"{self.title} > {self.section}"
        return f"{header}\n{self.text}"


_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")


def parse_sections(markdown: str) -> tuple[str, list[tuple[str, str]]]:
    """(doküman başlığı, [(bölüm yolu, gövde), ...]) döndürür."""
    title = ""
    path: list[str] = []          # h2 ve altı başlıklar
    sections: list[tuple[str, list[str]]] = [("", [])]

    for line in markdown.splitlines():
        m = _HEADING.match(line)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1:
                title = title or text
                path = []
            else:
                path = path[: level - 2] + [text]
            sections.append((" > ".join(path), []))
        else:
            sections[-1][1].append(line)

    result = []
    for sec_path, lines in sections:
        body = "\n".join(lines).strip()
        if body:
            result.append((sec_path, body))
    return title, result


def _blocks(body: str) -> list[tuple[str, str]]:
    """Gövdeyi ('table'|'text', metin) bloklarına ayırır."""
    blocks: list[tuple[str, str]] = []
    for raw in re.split(r"\n\s*\n", body):
        raw = raw.strip()
        if not raw:
            continue
        kind = "table" if all(l.lstrip().startswith("|") for l in raw.splitlines()) else "text"
        blocks.append((kind, raw))
    return blocks


def _split_table(text: str, size: int) -> list[str]:
    lines = text.splitlines()
    if len(text) <= size or len(lines) <= 3:
        return [text]
    header, rows = lines[:2], lines[2:]
    parts, cur = [], []
    for row in rows:
        candidate = "\n".join(header + cur + [row])
        if cur and len(candidate) > size:
            parts.append("\n".join(header + cur))
            cur = []
        cur.append(row)
    if cur:
        parts.append("\n".join(header + cur))
    return parts


def _tail(text: str, overlap: int) -> str:
    """Metnin son `overlap` karakterini kelime sınırından keserek döndürür."""
    if overlap <= 0 or len(text) <= overlap:
        return "" if overlap <= 0 else text
    tail = text[-overlap:]
    return tail[tail.find(" ") + 1 :] if " " in tail else ""


def _split_text(text: str, size: int, overlap: int) -> list[str]:
    if len(text) <= size:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    parts, cur = [], ""
    for s in sentences:
        if cur and len(cur) + 1 + len(s) > size:
            parts.append(cur)
            cur = f"{_tail(cur, overlap)} {s}".strip()
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        parts.append(cur)
    return parts


def chunk_section(body: str, size: int, overlap: int) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    for kind, text in _blocks(body):
        pieces = _split_table(text, size) if kind == "table" else _split_text(text, size, overlap)
        for piece in pieces:
            if cur and len("\n\n".join(cur)) + 2 + len(piece) > size:
                out.append("\n\n".join(cur))
                cur = []
            cur.append(piece)
    if cur:
        out.append("\n\n".join(cur))
    return out


def chunk_markdown(markdown: str, source: str, size: int = 600, overlap: int = 100) -> list[Chunk]:
    title, sections = parse_sections(markdown)
    stem = Path(source).stem
    chunks: list[Chunk] = []
    for sec_path, body in sections:
        for text in chunk_section(body, size, overlap):
            n = len(chunks)
            chunks.append(Chunk(f"{stem}-{n:03d}", text, source, title, sec_path, n))
    return chunks


def chunk_directory(docs_dir: Path, size: int = 600, overlap: int = 100) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        chunks.extend(chunk_markdown(path.read_text(encoding="utf-8"), path.name, size, overlap))
    return chunks
