from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse


VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mpeg", ".mpg"}


def is_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def safe_name(name: str, max_len: int = 100) -> str:
    name = re.sub(r"[^\w\-. ]+", "_", name, flags=re.UNICODE)
    name = re.sub(r"\s+", "_", name).strip("._")
    return (name[:max_len] or "video")


def probe_duration(video_path: str | Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    try:
        duration = float(result.stdout.strip())
    except ValueError as exc:
        raise ValueError(f"ffprobe вернул некорректную длительность: {result.stdout!r}") from exc
    if duration <= 0:
        raise ValueError(f"Некорректная длительность: {duration}")
    return duration


def has_audio(video_path: str | Path) -> bool:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(result.stdout.strip())
