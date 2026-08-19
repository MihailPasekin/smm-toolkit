from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class ValidationError(RuntimeError):
    pass


@dataclass
class VideoInfo:
    path: Path
    duration: float
    video_codec: str
    audio_codec: str | None
    width: int
    height: int
    fps: float
    has_audio: bool


def _run_ffprobe(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise ValidationError(
            "ffprobe не найден. Установите FFmpeg."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise ValidationError(
            f"ffprobe не смог прочитать файл: {detail[-1000:]}"
        ) from exc

    return result.stdout.strip()


def probe_video(path: str | Path) -> VideoInfo:
    path = Path(path)

    if not path.exists():
        raise ValidationError(f"Файл не существует: {path}")

    if not path.is_file():
        raise ValidationError(f"Это не файл: {path}")

    if path.stat().st_size <= 0:
        raise ValidationError(f"Файл пустой: {path}")

    duration_raw = _run_ffprobe([
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])

    video_raw = _run_ffprobe([
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,r_frame_rate",
        "-of",
        "csv=p=0",
        str(path),
    ])

    if not video_raw:
        raise ValidationError(
            f"Видео-поток не найден: {path}"
        )

    audio_raw = _run_ffprobe([
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_name",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])

    try:
        duration = float(duration_raw) 
        import math
        if not math.isfinite(duration):
            raise ValidationError(
            f"Некорректная длительность видео: {duration}"
                )
    except ValueError as exc:
        raise ValidationError(
            f"Некорректная длительность: {duration_raw!r}"
        ) from exc

    if duration <= 0:
        raise ValidationError(
            f"Некорректная длительность видео: {duration}"
        )

    parts = video_raw.split(",")

    if len(parts) < 4:
        raise ValidationError(
            f"Не удалось получить параметры video stream: {video_raw}"
        )

    codec = parts[0].strip()
    width = int(parts[1])
    height = int(parts[2])
    fps_raw = parts[3].strip()

    try:
        numerator, denominator = fps_raw.split("/")
        fps = float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        fps = 0.0

    if width <= 0 or height <= 0:
        if fps <= 0 or not math.isfinite(fps):
            raise ValidationError(f"Некорректный FPS: {fps_raw}")
        raise ValidationError(
            f"Некорректное разрешение: {width}x{height}"
        )

    return VideoInfo(
        path=path,
        duration=duration,
        video_codec=codec,
        audio_codec=audio_raw or None,
        width=width,
        height=height,
        fps=fps,
        has_audio=bool(audio_raw),
    )


def validate_decode(path: str | Path) -> None:
    path = Path(path)

    try:
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(path),
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        raise ValidationError(
            "ffmpeg не найден. Установите FFmpeg."
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()

        raise ValidationError(
            f"Видео не прошло decode-проверку: {detail[-1500:]}"
        ) from exc


def validate_video(path: str | Path) -> VideoInfo:
    """
    Full validation:
    - exists
    - non-empty
    - readable by ffprobe
    - has video stream
    - valid duration
    - valid resolution
    - decodes successfully
    """

    info = probe_video(path)
    validate_decode(path)

    return info


def validate_srt(path: str | Path, duration: float | None = None) -> int:
    path = Path(path)

    if not path.exists():
        raise ValidationError(
            f"SRT файл не существует: {path}"
        )

    if path.stat().st_size == 0:
        raise ValidationError(
            f"SRT файл пустой: {path}"
        )

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationError(
            f"SRT не является корректным UTF-8: {path}"
        ) from exc

    blocks = [
        block.strip()
        for block in text.split("\n\n")
        if block.strip()
    ]

    count = 0

    for block in blocks:
        lines = block.splitlines()

        if len(lines) < 3:
            raise ValidationError(
                f"Некорректный SRT block: {block!r}"
            )

        timestamp_line = lines[1]

        if " --> " not in timestamp_line:
            raise ValidationError(
                f"Некорректные timestamps: {timestamp_line!r}"
            )

        start_raw, end_raw = timestamp_line.split(" --> ", 1)

        start = _parse_srt_time(start_raw)
        end = _parse_srt_time(end_raw)

        if start >= end:
            raise ValidationError(
                f"SRT start >= end: {timestamp_line}"
            )

        if duration is not None and end > duration + 0.05:
            raise ValidationError(
                f"SRT timestamp выходит за длительность видео: "
                f"{timestamp_line}"
            )

        count += 1

    if count == 0:
        raise ValidationError(
            f"SRT не содержит subtitle blocks: {path}"
        )

    return count


def _parse_srt_time(value: str) -> float:
    try:
        hours, minutes, rest = value.split(":")
        seconds, milliseconds = rest.split(",")

        return (
            int(hours) * 3600
            + int(minutes) * 60
            + int(seconds)
            + int(milliseconds) / 1000
        )
    except (ValueError, AttributeError) as exc:
        raise ValidationError(
            f"Некорректный SRT timestamp: {value!r}"
        ) from exc