from __future__ import annotations

import subprocess
from pathlib import Path

from media import probe_duration


def render_cuts(video_path: str | Path, output_dir: str | Path, cuts) -> list[tuple[Path, float, float]]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    result = []

    for i, cut in enumerate(cuts): 
        start = cut.start
        end = cut.end
        output_file = output_dir / f"clip_{i + 1:03d}.mp4"

        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-ss", f"{start:.3f}", "-i", str(video_path),
            "-t", f"{end - start:.3f}",
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            str(output_file),
        ]
        subprocess.run(cmd, check=True)
        result.append((output_file, start, end))

    return result


def _escape_subtitles_filter_path(path: Path) -> str:
    # FFmpeg filtergraph escaping; works with spaces, apostrophes and drive/colon paths.
    value = str(path.resolve())
    value = value.replace("\\", "\\\\").replace(":", r"\:")
    value = value.replace("'", r"\'")
    value = value.replace("[", r"\[").replace("]", r"\]")
    return value


def burn_subtitles(video_path: str | Path, srt_path: str | Path,
                   output_path: str | Path) -> Path:
    srt_path = Path(srt_path)
    if not srt_path.exists():
        raise FileNotFoundError(f"SRT файл не найден: {srt_path}")
    if srt_path.stat().st_size == 0:
        raise ValueError(f"SRT файл пустой: {srt_path}")

    subtitle_path = _escape_subtitles_filter_path(srt_path)
    # Commas inside force_style are part of the ASS style value, but commas
    # also separate filter options in FFmpeg's filtergraph syntax. Escape them
    # explicitly or FFmpeg interprets FontSize/PrimaryColour/etc. as separate
    # filter options and fails with "No option name near ...".
    force_style = (
        "FontName=Arial\\,FontSize=24\\,PrimaryColour=&H00FFFFFF"
        "\\,OutlineColour=&H00000000\\,Outline=2\\,Alignment=2"
    )
    subtitle_filter = f"subtitles='{subtitle_path}':force_style='{force_style}'"

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", str(video_path),
        "-vf", subtitle_filter,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)
    return Path(output_path)


def split_video(video_path: str | Path, output_dir: str | Path,
                segment_duration: int) -> list[tuple[Path, float, float]]:
    """Compatibility wrapper for callers of the old V1 API."""
    from cut_strategy import FixedDurationCutStrategy
    duration = probe_duration(video_path)
    cuts = FixedDurationCutStrategy().plan(duration, segment_duration)
    return render_cuts(video_path, output_dir, cuts)
