from __future__ import annotations

import subprocess
import time
from pathlib import Path

try:
    from .errors import PipelineError
except ImportError:
    from errors import PipelineError


def extract_audio(video_path: str | Path, output_path: str | Path) -> Path:
    """Export the first audio stream from a media file as a portable MP3."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(video_path),
                "-vn",
                "-codec:a",
                "libmp3lame",
                "-b:a",
                "192k",
                str(output_path),
            ],
            check=True,
        )
    except FileNotFoundError as exc:
        raise PipelineError("Не найден ffmpeg. Установите FFmpeg.") from exc
    except subprocess.CalledProcessError as exc:
        raise PipelineError(f"Не удалось извлечь аудио: {exc}") from exc

    if not output_path.is_file() or output_path.stat().st_size == 0:
        raise PipelineError("FFmpeg не создал корректный MP3-файл.")

    return output_path


def download_audio(url: str, output_dir: str | Path) -> Path:
    """Download a URL directly as MP3 without retaining a video file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        "yt-dlp",
        "--no-playlist",
        "--extract-audio",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "0",
        "--print",
        "after_move:filepath",
        "-o",
        str(output_dir / "%(title)s.%(ext)s"),
        url,
    ]

    result = _run_ytdlp(command)
    candidates = [
        Path(line.strip())
        for line in result.stdout.splitlines()
        if line.strip()
    ]
    for candidate in reversed(candidates):
        if candidate.is_file() and candidate.suffix.lower() == ".mp3":
            return candidate

    files = list(output_dir.glob("*.mp3"))
    if len(files) == 1:
        return files[0]
    raise PipelineError("yt-dlp завершился, но MP3-файл не найден.")


def _run_ytdlp(command: list[str]) -> subprocess.CompletedProcess[str]:
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(1, 6):
        try:
            return subprocess.run(command, capture_output=True, text=True, check=True)
        except FileNotFoundError as exc:
            raise PipelineError("Не найден yt-dlp. Установите его: pip install yt-dlp") from exc
        except subprocess.CalledProcessError as exc:
            last_error = exc
            if attempt < 5:
                delay = 3 * attempt
                print(f"⚠️  yt-dlp попытка {attempt}/5 не удалась, повторяю через {delay}с...")
                time.sleep(delay)

    detail = (last_error.stderr or last_error.stdout or "yt-dlp завершился с ошибкой").strip()
    raise PipelineError(f"yt-dlp: {detail[-2000:]}") from last_error
