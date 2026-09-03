# scripts/media.py
from __future__ import annotations

from pathlib import Path
from datetime import datetime
from typing import Union

def is_url(string: str) -> bool:
    return string.startswith(("http://", "https://"))

def safe_name(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in " -_").strip()

def _resolve_output_root(output_root: Union[str, Path]) -> Path:
    root = Path(output_root).expanduser()
    if not root.is_absolute():
        root = Path(__file__).resolve().parent.parent / root
    root.mkdir(parents=True, exist_ok=True)
    return root

def _new_run_dir(output_root: Path, video_name: str) -> Path:
    candidate = output_root / video_name
    if not candidate.exists():
        return candidate
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_root / f"{video_name}_{timestamp}"

def probe_duration(media_path: Path) -> float:
    import subprocess
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(media_path)],
            capture_output=True, text=True, check=True
        )
        return float(result.stdout.strip())
    except Exception as exc:
        from errors import PipelineError
        raise PipelineError(f"Не удалось получить длительность: {exc}") from exc

def has_audio(video_path: Path) -> bool:
    import subprocess
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_type",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip() == "audio"
    except subprocess.CalledProcessError:
        return False
