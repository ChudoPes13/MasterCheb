"""Durable text-only sessions; SQLite transactions survive process restarts."""
import json
import sqlite3
import secrets
from datetime import datetime, timezone
from pathlib import Path

class SessionStore:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "mastercheb.sqlite3"
        with self.connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, updated TEXT NOT NULL, data TEXT NOT NULL)")

    def connection(self):
        return sqlite3.connect(self.path, timeout=10)

    def create(self, language: str, consent_version: str) -> dict:
        session = {"id": secrets.token_urlsafe(32), "language": language, "messages": [], "lead": {},
                   "stage": None, "submitted": False, "status": "new", "consent": consent_version,
                   "created": datetime.now(timezone.utc).isoformat()}
        self.save(session)
        return session

    def get(self, sid: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT data FROM sessions WHERE id=?", (sid,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, session: dict):
        session["updated"] = datetime.now(timezone.utc).isoformat()
        with self.connection() as db:
            db.execute("INSERT INTO sessions VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET updated=excluded.updated,data=excluded.data",
                       (session["id"], session["updated"], json.dumps(session, ensure_ascii=False)))

    def list(self, limit: int = 100, offset: int = 0):
        with self.connection() as db:
            return [json.loads(row[0]) for row in db.execute("SELECT data FROM sessions ORDER BY updated DESC LIMIT ? OFFSET ?", (limit, offset))]

    def delete(self, sid: str):
        with self.connection() as db:
            db.execute("DELETE FROM sessions WHERE id=?", (sid,))
