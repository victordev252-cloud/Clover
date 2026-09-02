from __future__ import annotations

import math, re, shutil
from pathlib import Path


def format_duration(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0: return "--:--"
    total = int(seconds); h, rem = divmod(total, 3600); m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def parse_timestamp(value: str) -> float:
    value = value.strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", value): return float(value)
    parts = value.split(":")
    if len(parts) not in (2, 3): raise ValueError("Use MM:SS or HH:MM:SS")
    try: nums = [float(x) for x in parts]
    except ValueError as exc: raise ValueError("Invalid timestamp") from exc
    if any(x < 0 for x in nums) or any(x >= 60 for x in nums[1:]): raise ValueError("Invalid timestamp range")
    return nums[-1] + nums[-2] * 60 + (nums[-3] * 3600 if len(nums) == 3 else 0)


def format_bytes(value: int) -> str:
    n = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB": return f"{n:.2f} {unit}"
        n /= 1024
    return "0 B"


def format_eta(seconds: float | None) -> str: return format_duration(seconds) if seconds is not None and math.isfinite(seconds) else "--:--"


def calculate_parts(duration: float, part_duration: float) -> list[tuple[float, float]]:
    if duration <= 0 or part_duration <= 0: raise ValueError("Durations must be positive")
    result=[]; start=0.0
    while start < duration - 1e-6:
        end=min(duration, start+part_duration); result.append((start,end)); start=end
    return result


def calculate_equal_parts(duration: float, count: int) -> list[tuple[float, float]]:
    if duration <= 0 or count < 2: raise ValueError("Invalid duration or part count")
    step=duration/count; return [(i*step, min(duration,(i+1)*step)) for i in range(count)]


def safe_filename(name: str, fallback: str = "video") -> str:
    stem = Path(name).stem or fallback
    stem = re.sub(r"[^\w .-]+", "_", stem, flags=re.UNICODE).strip(" .")[:100] or fallback
    return stem


def enough_space(path: Path, required: int) -> bool: return shutil.disk_usage(path).free >= required
