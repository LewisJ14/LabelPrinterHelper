import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional


class QueueStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.connection = sqlite3.connect(str(path), check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS print_jobs (
                report_id INTEGER PRIMARY KEY,
                checked_at TEXT,
                checked_by TEXT,
                serial_number TEXT,
                model TEXT,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                updated_at TEXT NOT NULL
            );
            """
        )
        self.connection.commit()

    def get_cursor(self) -> int:
        with self.lock:
            row = self.connection.execute(
                "SELECT value FROM settings WHERE key = 'report_cursor'"
            ).fetchone()
        return int(row["value"]) if row else 0

    def set_cursor(self, report_id: int) -> None:
        with self.lock:
            self.connection.execute(
                "INSERT INTO settings(key, value) VALUES('report_cursor', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (str(max(0, int(report_id))),),
            )
            self.connection.commit()

    def add_reports(self, reports: Iterable[Dict], selected_users: Iterable[str]) -> int:
        selected = {str(name).strip().casefold() for name in selected_users}
        added = 0
        now = datetime.now().isoformat(timespec="seconds")
        with self.lock:
            for report in reports:
                label = report.get("label") or {}
                checked_by = str(report.get("checked_by") or "Unknown").strip()
                status = "pending" if checked_by.casefold() in selected else "ignored"
                cursor = self.connection.execute(
                    """
                    INSERT OR IGNORE INTO print_jobs(
                        report_id, checked_at, checked_by, serial_number, model,
                        payload, status, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(report["report_id"]),
                        str(report.get("checked_at") or ""),
                        checked_by,
                        str(label.get("serial_number") or ""),
                        str(label.get("model") or ""),
                        json.dumps(report),
                        status,
                        now,
                    ),
                )
                added += int(cursor.rowcount > 0)
            self.connection.commit()
        return added

    def pending(self) -> List[Dict]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT * FROM print_jobs WHERE status = 'pending' ORDER BY report_id"
            ).fetchall()
        return [self._row(row) for row in rows]

    def recent(self, limit: int = 100) -> List[Dict]:
        with self.lock:
            rows = self.connection.execute(
                "SELECT * FROM print_jobs ORDER BY report_id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row(row) for row in rows]

    def get(self, report_id: int) -> Optional[Dict]:
        with self.lock:
            row = self.connection.execute(
                "SELECT * FROM print_jobs WHERE report_id = ?", (int(report_id),)
            ).fetchone()
        return self._row(row) if row else None

    def set_status(self, report_id: int, status: str, error: str = "") -> None:
        with self.lock:
            self.connection.execute(
                """
                UPDATE print_jobs
                SET status = ?, attempts = attempts + 1, last_error = ?, updated_at = ?
                WHERE report_id = ?
                """,
                (
                    status,
                    error[:1000],
                    datetime.now().isoformat(timespec="seconds"),
                    int(report_id),
                ),
            )
            self.connection.commit()

    def retry(self, report_id: int) -> None:
        with self.lock:
            self.connection.execute(
                "UPDATE print_jobs SET status = 'pending', last_error = '' "
                "WHERE report_id = ?",
                (int(report_id),),
            )
            self.connection.commit()

    @staticmethod
    def _row(row: sqlite3.Row) -> Dict:
        item = dict(row)
        item["payload"] = json.loads(item["payload"])
        return item
