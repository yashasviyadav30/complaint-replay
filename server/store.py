"""Where projects, reports and cases live: JSON documents in one table.

SQLite by default (a file, nothing to install: right for self-hosting). Set DATABASE_URL=postgresql://...
to use Postgres instead (for example a free Neon or Supabase database), which needs `pip install psycopg`.
ponytail: one generic table and filtering in Python; add real columns and indexes past ~100k documents.
"""

import json
import os
import sqlite3
import threading
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parent.parent / "results" / "complaint-replay.db"
SCHEMA = "CREATE TABLE IF NOT EXISTS docs (kind TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY (kind, id))"


class Store:
    def __init__(self, url: str = ""):
        url = url or os.getenv("DATABASE_URL", "")
        self._lock = threading.Lock()
        if url.startswith(("postgres://", "postgresql://")):
            import psycopg  # optional dependency, only for hosted deployments

            self._conn = psycopg.connect(url, autocommit=True)
            self._mark = "%s"
        else:
            path = Path(url.removeprefix("sqlite:///")) if url else DEFAULT_DB
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._mark = "?"
        self._sql(SCHEMA)
        m = self._mark
        self._put = (f"INSERT INTO docs (kind, id, data) VALUES ({m}, {m}, {m}) "
                     "ON CONFLICT (kind, id) DO UPDATE SET data = excluded.data")

    def _sql(self, query: str, args: tuple = ()) -> list[tuple]:
        with self._lock:
            cur = self._conn.execute(query, args)
            return cur.fetchall() if cur.description else []

    def put(self, kind: str, doc: dict) -> dict:
        self._sql(self._put, (kind, doc["id"], json.dumps(doc, ensure_ascii=False)))
        return doc

    def get(self, kind: str, doc_id: str) -> dict | None:
        m = self._mark
        rows = self._sql(f"SELECT data FROM docs WHERE kind = {m} AND id = {m}", (kind, doc_id))
        return json.loads(rows[0][0]) if rows else None

    def all(self, kind: str, **match) -> list[dict]:
        docs = [json.loads(r[0]) for r in self._sql(f"SELECT data FROM docs WHERE kind = {self._mark}", (kind,))]
        return [d for d in docs if all(d.get(k) == v for k, v in match.items())]

    def delete(self, kind: str, doc_id: str) -> None:
        m = self._mark
        self._sql(f"DELETE FROM docs WHERE kind = {m} AND id = {m}", (kind, doc_id))
