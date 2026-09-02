from __future__ import annotations

import asyncio, json, logging, os
from dataclasses import dataclass
from pathlib import Path
from typing import Awaitable, Callable

log = logging.getLogger("clover.media")

@dataclass(frozen=True)
class MediaInfo:
    duration: float; width: int; height: int; video_codec: str; audio_codec: str; format_name: str

async def probe(path: Path, ffprobe: str) -> MediaInfo:
    proc = await asyncio.create_subprocess_exec(ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await proc.communicate()
    if proc.returncode != 0: raise ValueError(f"ffprobe failed: {err.decode(errors='replace')[-500:]}")
    try: data=json.loads(out); fmt=data.get("format",{}); streams=data.get("streams",[]); video=next(s for s in streams if s.get("codec_type")=="video"); audio=next((s for s in streams if s.get("codec_type")=="audio"),{})
    except (json.JSONDecodeError, StopIteration) as exc: raise ValueError("File does not contain a valid video stream") from exc
    try: duration=float(fmt.get("duration",0))
    except (TypeError,ValueError): duration=0
    if not duration > 0: raise ValueError("Video duration is missing or invalid")
    return MediaInfo(duration, int(video.get("width") or 0), int(video.get("height") or 0), str(video.get("codec_name","unknown")), str(audio.get("codec_name","none")), str(fmt.get("format_name","unknown")))

async def split_part(input_path: Path, output_path: Path, start: float, end: float, mode: str, ffmpeg: str, on_progress: Callable[[float], Awaitable[None]] | None = None) -> None:
    duration=max(0.001,end-start); args=[ffmpeg,"-hide_banner","-y","-ss",f"{start:.3f}","-i",str(input_path),"-t",f"{duration:.3f}"]
    args += ["-map","0","-c","copy"] if mode == "fast" else ["-map","0","-c:v","libx264","-preset","veryfast","-crf","20","-c:a","aac","-b:a","128k"]
    args += ["-progress","pipe:1","-nostats",str(output_path)]
    proc=await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    async def read_progress():
        while True:
            line=await proc.stdout.readline()
            if not line: break
            if b"out_time_ms=" in line:
                try:
                    value=int(line.split(b"=",1)[1]); await on_progress(min(100.0,value/1000000/duration*100)) if on_progress else None
                except ValueError: pass
    progress=asyncio.create_task(read_progress())
    _, err=await proc.communicate(); await progress
    if proc.returncode != 0: raise RuntimeError(f"FFmpeg failed: {err.decode(errors='replace')[-1000:]}")
    if not output_path.exists() or output_path.stat().st_size == 0: raise RuntimeError("FFmpeg produced an empty part")
