from __future__ import annotations

import warnings
from pathlib import Path


def format_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    total_ms = round(seconds * 1000)
    hrs, rem = divmod(total_ms, 3_600_000)
    mins, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def transcribe_to_srt(video_path: str | Path, output_srt: str | Path) -> dict:
    # Whisper is imported only here, after the VAD gate has passed.
    warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")
    import whisper

    print(f"🎤 Распознаю речь: {video_path}")
    model = whisper.load_model("base")
    result = model.transcribe(str(video_path), fp16=False, verbose=False)
    segments = [
        segment for segment in result.get("segments", [])
        if segment.get("text", "").strip()
    ]

    output_srt = Path(output_srt)
    output_srt.parent.mkdir(parents=True, exist_ok=True)

    # Never leave an empty SRT behind. An empty transcription is a valid
    # outcome for --subtitles auto, and the renderer must simply be skipped.
    if not segments:
        output_srt.unlink(missing_ok=True)
        return {
            "language": result.get("language", "unknown"),
            "segments": [],
            "path": None,
            "generated": False,
            "reason": "whisper_no_segments",
        }

    _write_segments(segments, 0.0, float("inf"), output_srt)

    return {
        "language": result.get("language", "unknown"),
        "segments": segments,
        "path": str(output_srt),
        "generated": output_srt.exists() and output_srt.stat().st_size > 0,
        "reason": None,
    }


def _write_segments(segments, clip_start: float, clip_end: float, output_srt: Path) -> None:
    lines = []
    number = 1
    for segment in segments:
        seg_start = float(segment["start"])
        seg_end = float(segment["end"])
        overlap_start = max(seg_start, clip_start)
        overlap_end = min(seg_end, clip_end)
        if overlap_end <= overlap_start:
            continue

        # Critical V1.5 behavior: timestamps are shifted into clip-local time.
        local_start = overlap_start - clip_start
        local_end = overlap_end - clip_start
        text = segment.get("text", "").strip()
        if not text:
            continue
        lines.append(
            f"{number}\n{format_time(local_start)} --> {format_time(local_end)}\n{text}\n"
        )
        number += 1

    output_srt.write_text("\n".join(lines), encoding="utf-8")


def write_clip_srts(segments, clip_start: float, clip_end: float,
                    output_srt: str | Path) -> Path:
    output_srt = Path(output_srt)
    output_srt.parent.mkdir(parents=True, exist_ok=True)
    _write_segments(segments, clip_start, clip_end, output_srt)
    return output_srt


# Backwards-compatible CLI entrypoint.
def generate_subtitles(video_path: str, output_dir: str = "output") -> str:
    path = Path(output_dir) / f"{Path(video_path).stem}.srt"
    transcribe_to_srt(video_path, path)
    return str(path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Использование: python subtitles.py <путь_к_видео>")
        raise SystemExit(1)
    print(generate_subtitles(sys.argv[1]))
