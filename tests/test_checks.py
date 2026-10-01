import pytest

from eval.checks import Result, find_times, foreign_phone_numbers, looks_unknown, norm, run_checks

APPT = [{"start_at": "2026-09-30 14:00", "treatment_id": "kanal_tedavisi", "patient_name": "Ayşe Yılmaz"}]


def check(spec, text="", tools=(), cited=(), appts=(), has_tools=True):
    res = Result(text, [{"name": n, "input": {}, "is_error": False} for n in tools], list(cited), has_tools)
    return {c.name: c.passed for c in run_checks(spec, res, list(appts))}


def test_norm_folds_turkish_chars():
    assert norm("İPTAL Şişlik Ğ ı") == "iptal sislik g i"


def test_include_groups_all_required_any_within():
    spec = {"include": [["24"], ["48", "kirk sekiz"]]}
    assert all(check(spec, "24 saat ve 48 saat").values())
    assert not all(check(spec, "sadece 24 saat").values())


def test_exclude_and_regex():
    assert not check({"exclude": ["Ücretsiz"]}, "ücretsiz otopark")["exclude:Ücretsiz"]
    assert not check({"exclude_regex": [r"\d+\s*mg"]}, "500 mg alın")[r"exclude_regex:\d+\s*mg"]
    assert check({"exclude_regex": [r"\d+\s*mg"]}, "hekime danışın")[r"exclude_regex:\d+\s*mg"]


@pytest.mark.parametrize("text,expected", [
    ("Bu konuda elimde bilgi bulunmuyor, klinikle iletişime geçin.", True),
    ("Belgelerde otopark bilgisi yer almıyor.", True),
    ("Bilmiyorum.", True),
    ("Diş taşı temizliği 1.200 TL'dir [1].", False),
    ("Elimdeki bilgilere göre ücret 1.200 TL.", False),   # 'elimde' tek başına ret sayılmamalı
])
def test_looks_unknown(text, expected):
    assert looks_unknown(text) is expected


def test_unknown_check_both_directions():
    assert check({"unknown": True}, "Bilgi bulunmuyor.")["unknown"]
    assert not check({"unknown": False}, "Bilgi bulunmuyor.")["not_unknown"]


def test_citations():
    assert check({"cite_all": ["a.md", "b.md"]}, cited=["a.md", "b.md"])["cite_all"]
    assert not check({"cite_all": ["a.md", "b.md"]}, cited=["a.md"])["cite_all"]
    assert check({"cite_any": ["a.md", "b.md"]}, cited=["b.md"])["cite_any"]


def test_conflict_markers():
    assert check({"conflict_markers": True}, "Belgeler arasında çelişki var")["conflict_marker"]
    assert not check({"conflict_markers": True}, "48 saat.")["conflict_marker"]


def test_tool_checks_skipped_without_tools():
    r = check({"tools_called": ["check_slots"]}, has_tools=False)
    assert r == {}                                     # RAG'e haksız yere uygulanmaz
    assert not check({"tools_called": ["check_slots"]}, tools=[])["tools_called"]
    assert not check({"tools_not_called": ["book_appointment"]}, tools=["book_appointment"])["tools_not_called"]


def test_db_checks():
    assert check({"db_count": 1}, appts=APPT)["db_count"]
    assert not check({"db_count": 0}, appts=APPT)["db_count"]
    want = {"date": "2026-09-30", "time": "14:00", "treatment": "kanal_tedavisi", "name": "ayse yilmaz"}
    assert check({"db_has": want}, appts=APPT)["db_has"]
    assert not check({"db_has": {**want, "time": "15:00"}}, appts=APPT)["db_has"]


def test_alt_times_excludes_requested_slot():
    spec = {"alt_times": {"exclude": ["10:00"], "min": 1}}
    assert not check(spec, "10:00 dolu.")["alt_times"]
    assert check(spec, "10:00 dolu; 11:00 veya 14.30 uygun.")["alt_times"]
    assert find_times("saat 9:00 ve 09.30") == {"09:00", "09:30"}


def test_foreign_phone_detection():
    assert foreign_phone_numbers("Bizi 0216 555 01 23 numarasından arayın, acil için 112.") == []
    assert foreign_phone_numbers("Acil hattımız 0212 999 88 77") == ["02129998877"]
    assert foreign_phone_numbers("İmplant 25.000 TL, 22.000 TL'den başlar") == []


def test_asks_question():
    assert check({"asks_question": True}, "Hangi tedavi için?")["asks_question"]
    assert not check({"asks_question": True}, "Tamam.")["asks_question"]
