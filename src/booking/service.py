"""Randevu iş mantığı: müsaitlik sorgulama ve doğrulamalı rezervasyon."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from src.booking.schedule import (
    DOCTORS, MAX_HORIZON_DAYS, MIN_LEAD, TREATMENTS, WEEKDAYS_TR, candidate_starts,
)
from src.booking.store import AppointmentStore


class BookingError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


@dataclass(frozen=True)
class Appointment:
    id: int
    start: datetime
    end: datetime
    treatment: str
    doctor: str
    patient_name: str
    phone: str


def istanbul_now() -> datetime:
    return datetime.now(ZoneInfo("Europe/Istanbul")).replace(tzinfo=None)


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except (ValueError, AttributeError):
        raise BookingError("bad_date", "Tarih YYYY-AA-GG biçiminde olmalı (örn. 2026-10-02).")


def parse_time(value: str) -> datetime:
    try:
        return datetime.strptime(value.strip(), "%H:%M")
    except (ValueError, AttributeError):
        raise BookingError("bad_time", "Saat SS:DD biçiminde olmalı (örn. 14:30).")


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("90") and len(digits) == 12:
        digits = "0" + digits[2:]
    elif len(digits) == 10 and digits.startswith("5"):
        digits = "0" + digits
    if not re.fullmatch(r"05\d{9}", digits):
        raise BookingError("bad_phone", "Telefon geçerli bir cep numarası olmalı (örn. 0532 123 45 67).")
    return digits


def validate_name(raw: str) -> str:
    name = " ".join((raw or "").split())
    words = name.split(" ")
    if len(name) > 80 or len(words) < 2 or any(c in name for c in "<>{}[]\\;") or not all(
        any(ch.isalpha() for ch in w) for w in words
    ):
        raise BookingError("bad_name", "Hastanın ad ve soyadı gerekli.")
    return name


class BookingService:
    def __init__(self, store: AppointmentStore, now_fn=istanbul_now):
        self.store, self.now_fn = store, now_fn

    # ---- yardımcılar ----
    def _treatment(self, treatment_id: str):
        t = TREATMENTS.get(treatment_id)
        if not t:
            raise BookingError("bad_treatment", f"Bilinmeyen tedavi. Geçerli değerler: {', '.join(TREATMENTS)}")
        return t

    def _free_starts(self, day: date, treatment) -> list[tuple[datetime, str]]:
        now = self.now_fn()
        result = []
        for doc_id in treatment.doctor_ids:
            doctor = DOCTORS[doc_id]
            busy = self.store.busy(doc_id, day)
            for start in candidate_starts(day, treatment, doctor):
                end = start + timedelta(minutes=treatment.minutes)
                if start < now + MIN_LEAD:
                    continue
                if any(start < b_end and end > b_start for b_start, b_end in busy):
                    continue
                result.append((start, doc_id))
        return sorted(result)

    # ---- dışa açık işlemler ----
    def check_slots(self, day_str: str, treatment_id: str) -> dict:
        day, treatment = parse_date(day_str), self._treatment(treatment_id)
        today = self.now_fn().date()
        if day < today:
            raise BookingError("past_date", "Geçmiş bir tarih için randevu verilemez.")
        if day > today + timedelta(days=MAX_HORIZON_DAYS):
            raise BookingError("too_far", f"En fazla {MAX_HORIZON_DAYS} gün sonrasına randevu verilebilir.")

        slots = self._free_starts(day, treatment)
        out = {
            "date": day.isoformat(), "weekday": WEEKDAYS_TR[day.weekday()],
            "treatment": treatment.label, "duration_minutes": treatment.minutes,
            "slots": [{"time": s.strftime("%H:%M"), "doctor": DOCTORS[d].name} for s, d in slots],
        }
        if not slots:
            out["next_available"] = self.next_available(day, treatment_id)
        return out

    def next_available(self, after: date, treatment_id: str, horizon: int = 21) -> dict | None:
        treatment = self._treatment(treatment_id)
        for i in range(1, horizon + 1):
            d = after + timedelta(days=i)
            slots = self._free_starts(d, treatment)
            if slots:
                return {"date": d.isoformat(), "weekday": WEEKDAYS_TR[d.weekday()],
                        "first_times": [s.strftime("%H:%M") for s, _ in slots[:4]]}
        return None

    def book(self, day_str: str, time_str: str, treatment_id: str, patient_name: str, phone: str) -> Appointment:
        day, treatment = parse_date(day_str), self._treatment(treatment_id)
        start = datetime.combine(day, parse_time(time_str).time())
        name, phone = validate_name(patient_name), normalize_phone(phone)
        end = start + timedelta(minutes=treatment.minutes)
        now = self.now_fn()

        if start < now + MIN_LEAD:
            raise BookingError("too_soon", "Randevu en az 1 saat sonrası için alınabilir.")
        if day > now.date() + timedelta(days=MAX_HORIZON_DAYS):
            raise BookingError("too_far", f"En fazla {MAX_HORIZON_DAYS} gün sonrasına randevu verilebilir.")

        for doc_id in treatment.doctor_ids:
            if start not in candidate_starts(day, treatment, DOCTORS[doc_id]):
                continue
            appt_id = self.store.add_if_free(doc_id, treatment.id, start, end, name, phone, now)
            if appt_id:
                return Appointment(appt_id, start, end, treatment.label, DOCTORS[doc_id].name, name, phone)
        raise BookingError(
            "slot_unavailable",
            "Bu saat uygun değil (kapalı, çalışma saati dışında, öğle arası, hekim o gün yok ya da dolu). "
            "check_slots ile müsait saatleri sorgulayın.",
        )
