"""SQLite randevu deposu. Çift rezervasyon, tek işlemde (BEGIN IMMEDIATE) engellenir."""
from __future__ import annotations

import sqlite3
import threading
from datetime import date, datetime, timedelta

FMT = "%Y-%m-%d %H:%M"

SCHEMA = """
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id TEXT NOT NULL,
    treatment_id TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    patient_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_doctor_start ON appointments (doctor_id, start_at);
"""


class AppointmentStore:
    def __init__(self, path: str = ":memory:"):
        self._conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.executescript(SCHEMA)

    def busy(self, doctor_id: str, day: date) -> list[tuple[datetime, datetime]]:
        lo = datetime.combine(day, datetime.min.time())
        hi = lo + timedelta(days=1)
        with self._lock:
            rows = self._conn.execute(
                "SELECT start_at, end_at FROM appointments "
                "WHERE doctor_id=? AND status='confirmed' AND start_at>=? AND start_at<?",
                (doctor_id, lo.strftime(FMT), hi.strftime(FMT)),
            ).fetchall()
        return [(datetime.strptime(s, FMT), datetime.strptime(e, FMT)) for s, e in rows]

    def all_confirmed(self) -> list[dict]:
        """Tüm onaylı randevular (test ve değerlendirme için)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, doctor_id, treatment_id, start_at, end_at, patient_name, phone "
                "FROM appointments WHERE status='confirmed' ORDER BY start_at"
            ).fetchall()
        keys = ["id", "doctor_id", "treatment_id", "start_at", "end_at", "patient_name", "phone"]
        return [dict(zip(keys, r)) for r in rows]

    def add_if_free(self, doctor_id, treatment_id, start: datetime, end: datetime,
                    name: str, phone: str, created_at: datetime) -> int | None:
        """Aralık boşsa kaydeder ve id döndürür; doluysa None."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                clash = self._conn.execute(
                    "SELECT 1 FROM appointments WHERE doctor_id=? AND status='confirmed' "
                    "AND start_at < ? AND end_at > ?",
                    (doctor_id, end.strftime(FMT), start.strftime(FMT)),
                ).fetchone()
                if clash:
                    self._conn.execute("ROLLBACK")
                    return None
                cur = self._conn.execute(
                    "INSERT INTO appointments (doctor_id, treatment_id, start_at, end_at, "
                    "patient_name, phone, created_at) VALUES (?,?,?,?,?,?,?)",
                    (doctor_id, treatment_id, start.strftime(FMT), end.strftime(FMT),
                     name, phone, created_at.strftime(FMT)),
                )
                self._conn.execute("COMMIT")
                return cur.lastrowid
            except Exception:
                self._conn.execute("ROLLBACK")
                raise
