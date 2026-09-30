"""Klinik takvim kuralları (saf mantık, veritabanı yok).

Kaynak: data/docs/04_calisma_saatleri.md. Cumartesi için SSS ile çelişki var (17:00 / 14:00);
resmi çalışma saatleri belgesi esas alınmıştır.
Varsayımlar (belgede yok): randevu için en az 1 saat önceden, en fazla 60 gün ilerisi.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

SLOT_MINUTES = 30
MIN_LEAD = timedelta(hours=1)
MAX_HORIZON_DAYS = 60

WEEKDAYS_TR = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

# 0=Pazartesi ... 6=Pazar (Pazar kapalı)
OPENING_HOURS = {
    **{d: (time(9, 0), time(18, 0)) for d in range(5)},
    5: (time(9, 0), time(14, 0)),
}
LUNCH = (time(12, 30), time(13, 30))

# Resmi tatiller elle girilir; yıl başında doğrula.
HOLIDAYS = {date(2026, 10, 29), date(2027, 1, 1)}


@dataclass(frozen=True)
class Doctor:
    id: str
    name: str
    weekdays: frozenset[int]


@dataclass(frozen=True)
class Treatment:
    id: str
    label: str
    minutes: int
    doctor_ids: tuple[str, ...]


DOCTORS = {
    d.id: d
    for d in [
        Doctor("elif_kaya", "Dr. Elif Kaya", frozenset({0, 1, 2, 3, 4})),
        Doctor("murat_aydin", "Dr. Murat Aydın", frozenset({1, 3, 5})),
        Doctor("selin_arslan", "Dr. Selin Arslan", frozenset({0, 2, 4})),
    ]
}

TREATMENTS = {
    t.id: t
    for t in [
        Treatment("muayene", "Muayene ve panoramik röntgen", 30, ("elif_kaya",)),
        Treatment("dis_tasi", "Diş taşı temizliği", 60, ("elif_kaya",)),
        Treatment("dolgu", "Dolgu", 60, ("elif_kaya",)),
        Treatment("kanal_tedavisi", "Kanal tedavisi", 90, ("elif_kaya",)),
        Treatment("dis_cekimi", "Diş çekimi (basit)", 30, ("elif_kaya",)),
        Treatment("cerrahi_cekim", "Yirmilik / cerrahi diş çekimi", 60, ("murat_aydin",)),
        Treatment("implant", "İmplant", 120, ("murat_aydin",)),
        Treatment("beyazlatma", "Diş beyazlatma", 60, ("elif_kaya",)),
        Treatment("seffaf_plak", "Şeffaf plak (ilk görüşme ve planlama)", 60, ("selin_arslan",)),
    ]
}


def candidate_starts(day: date, treatment: Treatment, doctor: Doctor) -> list[datetime]:
    """Kuralları (çalışma saati, öğle arası, hekim günü, tatil) sağlayan tüm başlangıç saatleri."""
    hours = OPENING_HOURS.get(day.weekday())
    if hours is None or day in HOLIDAYS or day.weekday() not in doctor.weekdays:
        return []
    close = datetime.combine(day, hours[1])
    lunch_start, lunch_end = datetime.combine(day, LUNCH[0]), datetime.combine(day, LUNCH[1])
    duration = timedelta(minutes=treatment.minutes)

    starts, t = [], datetime.combine(day, hours[0])
    while t + duration <= close:
        end = t + duration
        if not (t < lunch_end and end > lunch_start):  # öğle arasıyla kesişmesin
            starts.append(t)
        t += timedelta(minutes=SLOT_MINUTES)
    return starts
