from pathlib import Path

from src.ingest.chunking import chunk_directory, chunk_markdown, parse_sections

DOC = """# Klinik

## Kanal tedavisi
Tek kanallı dişte 1 seans gerekir.

## Diş çekimi
Basit çekim 20 dakika sürer.

### Sonrası
24 saat sıcak yiyecek yemeyin.
"""

TABLE = "# Fiyat\n\n" + "| Tedavi | Fiyat |\n|---|---|\n" + "\n".join(
    f"| Tedavi {i} | {i * 100} TL |" for i in range(40)
)


def test_sections_and_title():
    title, sections = parse_sections(DOC)
    assert title == "Klinik"
    assert [s for s, _ in sections] == ["Kanal tedavisi", "Diş çekimi", "Diş çekimi > Sonrası"]


def test_one_chunk_per_short_section():
    chunks = chunk_markdown(DOC, "k.md")
    assert len(chunks) == 3
    assert chunks[0].id == "k-000"
    assert "Klinik > Kanal tedavisi" in chunks[0].contextual_text


def test_long_table_split_repeats_header():
    chunks = chunk_markdown(TABLE, "f.md", size=300)
    assert len(chunks) > 1
    for c in chunks:
        assert c.text.startswith("| Tedavi | Fiyat |")
        assert len(c.text) <= 300 + 60  # başlık payı


def test_long_paragraph_split_with_overlap():
    para = " ".join(f"Cümle numara {i} burada yer alıyor." for i in range(30))
    chunks = chunk_markdown(f"# D\n\n## B\n{para}", "d.md", size=200, overlap=60)
    assert len(chunks) > 2
    # ardışık chunk'larda ortak kelime olmalı (overlap)
    a, b = chunks[0].text.split(), chunks[1].text.split()
    assert set(a[-6:]) & set(b[:8])


def test_no_empty_chunks_on_real_docs():
    docs = Path(__file__).resolve().parents[1] / "data" / "docs"
    chunks = chunk_directory(docs)
    assert chunks and all(c.text.strip() for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)
