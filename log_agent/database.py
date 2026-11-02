import sqlite3
import json
from pathlib import Path
from datetime import datetime

class IncidentDB:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    question TEXT NOT NULL,
                    summary TEXT,
                    report_json TEXT NOT NULL
                )
            """)

    def _connect(self):
        return sqlite3.connect(self.path)

    def save(self, question, report):
        with self._connect() as con:
            con.execute(
                "INSERT INTO incidents(created_at, question, summary, report_json) VALUES(?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), question,
                 report.get("summary", ""), json.dumps(report, ensure_ascii=False, default=str))
            )

    def history(self, limit=50):
        with self._connect() as con:
            rows = con.execute(
                "SELECT id, created_at, question, summary FROM incidents ORDER BY id DESC LIMIT ?",
                (int(limit),)
            ).fetchall()
        return rows
