from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _float(name: str, default: float, minimum: float = 0.0) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    bot_token: str
    admin_ids: frozenset[int]
    max_file_size_gb: float
    max_parts: int
    max_concurrent_jobs: int
    max_active_jobs_per_user: int
    min_free_space_gb: float
    progress_update_interval: int
    cleanup_after_hours: int
    ffmpeg_path: str
    ffprobe_path: str
    database_path: Path
    download_dir: Path
    log_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("BOT_TOKEN is required. Copy .env.example to .env and configure it.")
        admins = frozenset(int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip())
        return cls(
            api_id=_int("API_ID", 0), api_hash=os.getenv("API_HASH", ""), bot_token=token,
            admin_ids=admins, max_file_size_gb=_float("MAX_FILE_SIZE_GB", 4, 0.1),
            max_parts=_int("MAX_PARTS", 100, 2), max_concurrent_jobs=_int("MAX_CONCURRENT_JOBS", 2, 1),
            max_active_jobs_per_user=_int("MAX_ACTIVE_JOBS_PER_USER", 1, 1),
            min_free_space_gb=_float("MIN_FREE_SPACE_GB", 2, 0),
            progress_update_interval=_int("PROGRESS_UPDATE_INTERVAL", 3, 1),
            cleanup_after_hours=_int("CLEANUP_AFTER_HOURS", 6, 1),
            ffmpeg_path=os.getenv("FFMPEG_PATH", "ffmpeg"), ffprobe_path=os.getenv("FFPROBE_PATH", "ffprobe"),
            database_path=Path(os.getenv("DATABASE_PATH", "data/clover.db")),
            download_dir=Path(os.getenv("DOWNLOAD_DIR", "data/jobs")), log_dir=Path(os.getenv("LOG_DIR", "logs")),
        )

    def prepare(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)


settings = Settings.from_env() if os.getenv("BOT_TOKEN") else None
