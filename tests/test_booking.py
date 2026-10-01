from datetime import date, datetime

import pytest

from src.booking.service import BookingError, BookingService, normalize_phone, validate_name
from src.booking.store import AppointmentStore

NOW = datetime(2026, 9, 29, 10, 0)  # Salı 10:00


@pytest.fixture
def svc():
    return BookingService(AppointmentStore(":memory:"), now_fn=lambda: NOW)


def times(res):
    return [s["time"] for s in res["slots"]]


def test_sunday_closed_and_suggests_next(svc):
    res = svc.check_slots("2026-10-04", "muayene")  # Pazar
    assert res["slots"] == []
    assert res["next_available"]["date"] == "2026-10-05"  # Pazartesi


def test_lunch_break_respected_for_long_treatment(svc):
    t = times(svc.check_slots("2026-09-30", "kanal_tedavisi"))  # Çarşamba, 90 dk
    assert "11:00" in t            # 12:30'da biter, öğle arasına girmez
    assert not {"11:30", "12:00", "12:30", "13:00"} & set(t)
    assert "13:30" in t and t[-1] == "16:30"


def test_saturday_closes_at_14(svc):
    t = times(svc.check_slots("2026-10-03", "implant"))  # Cumartesi, Dr. Murat, 120 dk
    assert t == ["09:00", "09:30", "10:00", "10:30"]


def test_doctor_weekdays(svc):
    assert svc.check_slots("2026-10-05", "implant")["slots"] == []       # Pazartesi Dr. Murat yok
    assert times(svc.check_slots("2026-10-06", "implant"))               # Salı var


def test_holiday_closed(svc):
    assert svc.check_slots("2026-10-29", "implant")["slots"] == []


def test_lead_time_today(svc):
    t = times(svc.check_slots("2026-09-29", "muayene"))
    assert t[0] == "11:00"  # 10:00 + 1 saat


def test_past_date_and_bad_input(svc):
    with pytest.raises(BookingError) as e:
        svc.check_slots("2026-09-28", "muayene")
    assert e.value.code == "past_date"
    with pytest.raises(BookingError):
        svc.check_slots("yarın", "muayene")
    with pytest.raises(BookingError):
        svc.check_slots("2026-09-30", "bilinmeyen")


def test_book_and_no_double_booking(svc):
    a = svc.book("2026-09-30", "10:00", "dolgu", "Ayşe Yılmaz", "0532 123 45 67")
    assert a.doctor == "Dr. Elif Kaya" and a.end.strftime("%H:%M") == "11:00"
    with pytest.raises(BookingError) as e:
        svc.book("2026-09-30", "10:00", "dolgu", "Mehmet Demir", "05321234568")
    assert e.value.code == "slot_unavailable"


def test_partial_overlap_blocked_then_adjacent_ok(svc):
    svc.book("2026-09-30", "10:00", "dolgu", "Ayşe Yılmaz", "05321234567")   # 10:00-11:00
    with pytest.raises(BookingError):
        svc.book("2026-09-30", "10:30", "muayene", "Ali Veli", "05321234568")
    svc.book("2026-09-30", "11:00", "muayene", "Ali Veli", "05321234568")     # hemen sonrası serbest
    assert "10:00" not in times(svc.check_slots("2026-09-30", "muayene"))


def test_cannot_book_past_or_too_soon(svc):
    for d, t in [("2026-09-29", "09:00"), ("2026-09-29", "10:30")]:
        with pytest.raises(BookingError) as e:
            svc.book(d, t, "muayene", "Ali Veli", "05321234568")
        assert e.value.code == "too_soon"


def test_cannot_book_outside_rules(svc):
    with pytest.raises(BookingError):
        svc.book("2026-10-04", "10:00", "muayene", "Ali Veli", "05321234568")   # Pazar
    with pytest.raises(BookingError):
        svc.book("2026-09-30", "12:30", "muayene", "Ali Veli", "05321234568")   # öğle arası
    with pytest.raises(BookingError):
        svc.book("2026-09-30", "10:15", "muayene", "Ali Veli", "05321234568")   # ızgara dışı


@pytest.mark.parametrize("raw,expected", [
    ("0532 123 45 67", "05321234567"), ("+90 532 123 45 67", "05321234567"), ("532-123-4567", "05321234567"),
])
def test_phone_normalization(raw, expected):
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["12345", "02161234567", "abc", ""])
def test_bad_phone(raw):
    with pytest.raises(BookingError):
        normalize_phone(raw)


@pytest.mark.parametrize("raw", ["Ayşe", "", "<script> x", "1 2"])
def test_bad_name(raw):
    with pytest.raises(BookingError):
        validate_name(raw)
