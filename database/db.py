from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, last_name TEXT, language TEXT DEFAULT 'en', created_at TEXT DEFAULT CURRENT_TIMESTAMP, last_seen TEXT DEFAULT CURRENT_TIMESTAMP, is_blocked INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS jobs (job_id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, filename TEXT NOT NULL, file_size INTEGER DEFAULT 0, duration REAL DEFAULT 0, width INTEGER, height INTEGER, video_codec TEXT, audio_codec TEXT, mode TEXT, output_format TEXT DEFAULT 'mp4', parts_count INTEGER DEFAULT 0, part_duration REAL, status TEXT NOT NULL, progress REAL DEFAULT 0, current_part INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, started_at TEXT, completed_at TEXT, error_message TEXT);
CREATE TABLE IF NOT EXISTS job_parts (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE, part_number INTEGER NOT NULL, start_time REAL NOT NULL, end_time REAL NOT NULL, duration REAL NOT NULL, file_size INTEGER DEFAULT 0, status TEXT DEFAULT 'PENDING', uploaded INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP, completed_at TEXT, UNIQUE(job_id, part_number));
CREATE TABLE IF NOT EXISTS settings (user_id INTEGER PRIMARY KEY, split_mode TEXT DEFAULT 'fast', output_format TEXT DEFAULT 'mp4', progress_enabled INTEGER DEFAULT 1, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS blocked_users (user_id INTEGER PRIMARY KEY, reason TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS statistics (key TEXT PRIMARY KEY, value INTEGER DEFAULT 0, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS system_events (id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT, user_id INTEGER, job_id TEXT, details TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id); CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status); CREATE INDEX IF NOT EXISTS idx_parts_job ON job_parts(job_id);
"""

class Database:
    def __init__(self, path: Path):
        self.path = path
        self._lock = asyncio.Lock()

    async def init(self) -> None:
        async with self._lock:
            await asyncio.to_thread(self._run, SCHEMA, ())

    def _run(self, sql: str, params: tuple[Any, ...] = (), fetch: str | None = None):
        with sqlite3.connect(self.path) as con:
            con.row_factory = sqlite3.Row
            cur = con.execute(sql, params)
            con.commit()
            if fetch == "one":
                row = cur.fetchone(); return dict(row) if row else None
            if fetch == "all": return [dict(r) for r in cur.fetchall()]
            return cur.lastrowid

    async def execute(self, sql: str, params: tuple[Any, ...] = ()):
        async with self._lock: return await asyncio.to_thread(self._run, sql, params)

    async def one(self, sql: str, params: tuple[Any, ...] = ()):
        async with self._lock: return await asyncio.to_thread(self._run, sql, params, "one")

    async def all(self, sql: str, params: tuple[Any, ...] = ()):
        async with self._lock: return await asyncio.to_thread(self._run, sql, params, "all")

    async def upsert_user(self, user) -> None:
        await self.execute("INSERT INTO users(user_id,username,first_name,last_name) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,first_name=excluded.first_name,last_name=excluded.last_name,last_seen=CURRENT_TIMESTAMP", (user.id, user.username, user.first_name, user.last_name))

    async def is_blocked(self, user_id: int) -> bool:
        return bool(await self.one("SELECT 1 FROM blocked_users WHERE user_id=?", (user_id,)))

    async def active_for_user(self, user_id: int):
        return await self.one("SELECT * FROM jobs WHERE user_id=? AND status IN ('QUEUED','DOWNLOADING','VALIDATING','WAITING','PROCESSING','UPLOADING') ORDER BY created_at DESC LIMIT 1", (user_id,))

    async def stats(self):
        return await self.all("SELECT status,COUNT(*) AS count FROM jobs GROUP BY status")

    async def close(self):
        return None
