from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


try:
    from .media import has_audio, is_url, probe_duration, safe_name
    from .speech import has_speech
    from .subtitles import transcribe_to_srt, write_clip_srts
    from .render import burn_subtitles, render_cuts
    from .cut_strategy import FixedDurationCutStrategy
    from .validator import validate_video, validate_srt, ValidationError
except ImportError:
    from media import has_audio, is_url, probe_duration, safe_name
    from speech import has_speech
    from subtitles import transcribe_to_srt, write_clip_srts
    from render import burn_subtitles, render_cuts
    from cut_strategy import FixedDurationCutStrategy
    from validator import validate_video, validate_srt, ValidationError

VERSION = "1.5.0"


class PipelineError(RuntimeError):
    pass


@dataclass
class ClipInfo:
    index: int
    path: str
    start: float
    end: float
    duration: float
    subtitle_path: str | None = None


@dataclass
class Metadata:
    version: str
    created_at: str
    source_input: str
    source_path: str
    source_url: str | None
    source_filename: str
    duration: float
    segment_duration: int
    was_split: bool
    speech_detected: bool
    subtitles_mode: str
    subtitles_generated: bool
    subtitles_skipped_reason: str | None
    transcription_attempted: bool
    transcription_segments: int
    detected_language: str | None
    clips: list[ClipInfo]
    errors: list[str]



def normalize_video(video_path: str | Path) -> Path:
    """
    Ensure the video is a broadly compatible MP4:
    H.264 video + AAC audio.

    If the downloaded file already uses a compatible codec,
    it is returned unchanged.
    """

    video_path = Path(video_path)

    if not video_path.exists():
        raise PipelineError(
            f"Скачанный файл не существует: {video_path}"
        )

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        video_codec = result.stdout.strip().lower()

    except subprocess.CalledProcessError as exc:
        raise PipelineError(
            f"Не удалось определить видеокодек: {exc}"
        ) from exc

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        audio_codec = result.stdout.strip().lower()

    except subprocess.CalledProcessError:
        audio_codec = ""

    compatible = (
        video_path.suffix.lower() == ".mp4"
        and video_codec in {"h264"}
        and audio_codec in {"aac", ""}
    )

    if compatible:
        return video_path

    normalized = video_path.with_name(
        f"{video_path.stem}_normalized.mp4"
    )

    print(
        f"🔄 Нормализация видео: "
        f"{video_codec or 'unknown'} + "
        f"{audio_codec or 'no audio'} → H.264 + AAC"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-i",
        str(video_path),

        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",

        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",

        "-c:a",
        "aac",
        "-b:a",
        "192k",

        "-movflags",
        "+faststart",

        str(normalized),
    ]

    try:
        subprocess.run(cmd, check=True)
    except FileNotFoundError as exc:
        raise PipelineError(
            "Не найден ffmpeg. Установите FFmpeg."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise PipelineError(
            f"FFmpeg не смог нормализовать видео: {exc}"
        ) from exc

    if not normalized.exists() or normalized.stat().st_size == 0:
        raise PipelineError(
            "FFmpeg не создал корректный нормализованный файл."
        )

    # Validate the resulting MP4 before returning it.
    try:
        subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(normalized),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        normalized.unlink(missing_ok=True)
        raise PipelineError(
            "Нормализованное видео прошло кодирование, "
            "но не прошло проверку ffprobe."
        ) from exc

    video_path.unlink(missing_ok=True)

    return normalized


def download_video(url: str, output_dir: str | Path) -> Path:
    """Download a video and normalize it to a widely compatible MP4."""

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    template = str(output_dir / "%(title)s.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f",
        "best[protocol^=m3u8]/best[ext=mp4]/best",
        "--merge-output-format",
        "mp4",
        "--print",
        "after_move:filepath",
        "-o",
        template,
        url,
    ]

    # YouTube's served format list (and which formats have a working PO
    # Token) varies between requests, so a single attempt can 403 on a
    # format that would succeed moments later. Retry a few times before
    # giving up.
    max_attempts = 5
    result = None
    last_error: subprocess.CalledProcessError | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            break
        except FileNotFoundError as exc:
            raise PipelineError(
                "Не найден yt-dlp. Установите его: pip install yt-dlp"
            ) from exc
        except subprocess.CalledProcessError as exc:
            last_error = exc
            if attempt < max_attempts:
                delay = 3 * attempt
                print(
                    f"⚠️  yt-dlp попытка {attempt}/{max_attempts} "
                    f"не удалась, повторяю через {delay}с..."
                )
                time.sleep(delay)

    if result is None:
        detail = (
            last_error.stderr
            or last_error.stdout
            or "yt-dlp завершился с ошибкой"
        ).strip()

        raise PipelineError(
            f"yt-dlp: {detail[-2000:]}"
        ) from last_error

    candidates = [
        Path(line.strip())
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    downloaded = None

    for candidate in reversed(candidates):
        if candidate.exists() and candidate.is_file():
            downloaded = candidate
            break

    if downloaded is None:
        files = [
            p for p in output_dir.iterdir()
            if p.is_file()
        ]

        if len(files) == 1:
            downloaded = files[0]

    if downloaded is None:
        raise PipelineError(
            "yt-dlp завершился, но скачанный файл не найден."
        )

    normalized = normalize_video(downloaded)

    try:
        validate_video(normalized)
    except ValidationError as exc:
        raise PipelineError(
            f"Скачанное видео не прошло проверку: {exc}"
        ) from exc

    return normalized


def _resolve_output_root(output_root: str | Path) -> Path:
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


def run_pipeline(
    source: str,
    segment_duration: int = 60,
    subtitles: str = "auto",
    output_root: str | Path = "output",
) -> Path:
    if segment_duration <= 0:
        raise PipelineError("segment_duration должен быть больше 0.")
    if subtitles not in {"auto", "yes", "no"}:
        raise PipelineError("--subtitles должен быть auto, yes или no.")
    if not source or not source.strip():
        raise PipelineError("Источник видео не указан.")

    output_root = _resolve_output_root(output_root)
    source_url = source if is_url(source) else None
    source_path = Path(source).expanduser().resolve()

    with tempfile.TemporaryDirectory(prefix="smm_toolkit_") as tmp:
        tmp_dir = Path(tmp)
        if source_url:
            print(f"⬇️  Скачивание: {source_url}")
            source_path = download_video(source_url, tmp_dir)
        elif not source_path.exists():
            raise PipelineError(f"Файл не найден: {source_path}")
        elif not source_path.is_file():
            raise PipelineError(f"Это не файл: {source_path}")
        try:
            video_info = validate_video(source_path)
            duration = video_info.duration
        except ValidationError as exc:
            raise PipelineError(
                f"Видео не прошло проверку: {exc}" ) from exc
        
        video_name = safe_name(source_path.stem)
        run_dir = _new_run_dir(output_root, video_name)
        source_dir = run_dir / "source"
        clips_dir = run_dir / "clips"
        subs_dir = run_dir / "subtitles"
        source_dir.mkdir(parents=True)
        clips_dir.mkdir()
        subs_dir.mkdir()

        stored_source = source_dir / source_path.name
        shutil.copy2(source_path, stored_source)

        errors: list[str] = []
        speech_detected = False
        subtitles_generated = False
        subtitles_skipped_reason: str | None = None
        transcription_attempted = False
        transcription_segments = 0
        detected_language: str | None = None
        subtitle_data = None

        # VAD is the gate. Whisper is imported only by transcribe_to_srt after
        # VAD has confirmed speech.
        if subtitles != "no":
            try:
                audio_present = has_audio(stored_source)
            except Exception as exc:
                if subtitles == "yes":
                    raise PipelineError(f"Не удалось проверить аудиодорожку: {exc}") from exc
                errors.append(f"audio detection skipped: {exc}")
                audio_present = False

            if audio_present:
                try:
                    speech_detected = has_speech(stored_source)
                except Exception as exc:
                    if subtitles == "yes":
                        raise PipelineError(f"Не удалось определить наличие речи: {exc}") from exc
                    errors.append(f"speech detection skipped: {exc}")

        should_subtitle = subtitles == "yes" or (subtitles == "auto" and speech_detected)
        if should_subtitle:
            transcription_attempted = True
            try:
                subtitle_data = transcribe_to_srt(
                    stored_source,
                    subs_dir / "source.srt",
                )
                detected_language = subtitle_data.get("language")
                transcription_segments = len(subtitle_data.get("segments", []))

                if subtitle_data.get("generated") and subtitle_data.get("segments"):
                    subtitles_generated = True
                else:
                    subtitles_skipped_reason = subtitle_data.get(
                        "reason", "whisper_no_segments"
                    )
                    message = (
                        "Whisper не обнаружил распознаваемую речь; "
                        "видео будет сохранено без субтитров."
                    )
                    if subtitles == "yes":
                        raise PipelineError(message)
                    errors.append(message)

            except PipelineError:
                raise
            except Exception as exc:
                subtitles_skipped_reason = "transcription_error"
                if subtitles == "yes":
                    raise PipelineError(f"Не удалось создать субтитры: {exc}") from exc
                errors.append(f"subtitle generation skipped: {exc}")

        # Architecture boundary for future Smart Cut.
        strategy = FixedDurationCutStrategy()
        cuts = strategy.plan(duration, segment_duration)
        was_split = len(cuts) > 1

        if was_split:
            print(f"✂️  {duration:.1f}с → режу на {segment_duration}с")
            raw_clips = render_cuts(stored_source, clips_dir, cuts)
                
        else:
            print(f"⏭️  {duration:.1f}с → короче лимита, не режу")
            raw_clips = [(stored_source, 0.0, duration)]

        clips: list[ClipInfo] = []
        for idx, (clip_path, start, end) in enumerate(raw_clips, 1):
            final_path = Path(clip_path)
            subtitle_path = None
            try:
                clip_info = validate_video(clip_path)
            except ValidationError as exc:
                raise PipelineError(
                    f"Clip {idx:03d} не прошёл проверку: {exc}"
                ) from exc
            expected_duration = end - start

            if abs(clip_info.duration - expected_duration) > 1.0:
                raise PipelineError(
                    f"Clip {idx:03d} имеет неправильную длительность: "
                    f"{clip_info.duration:.3f}s вместо "
                    f"{expected_duration:.3f}s"
                )
            if subtitles_generated and subtitle_data:
                subtitle_path = subs_dir / f"clip_{idx:03d}.srt"
                write_clip_srts(
                    subtitle_data["segments"],
                    start,
                    end,
                    subtitle_path,)
                try:
                    validate_srt(subtitle_path,duration=end - start,)
                except ValidationError as exc:
                    raise PipelineError(
                   f"Сгенерированный SRT для clip_{idx:03d} "
                 f"не прошёл проверку: {exc}"
                ) from exc
                burned = clips_dir / f"clip_{idx:03d}_subtitled.mp4"
                try:
                    burn_subtitles(final_path, subtitle_path, burned)
                except subprocess.CalledProcessError as exc:
                    raise PipelineError(f"Не удалось наложить субтитры на clip_{idx:03d}: {exc}") from exc

                try:
                    validate_video(burned)
                except ValidationError as exc:
                    raise PipelineError(
                        f"Готовый clip_{idx:03d}_subtitled.mp4 "
                        f"не прошёл проверку: {exc}"
                    ) from exc
                if final_path != stored_source:
                    final_path.unlink(missing_ok=True)
                final_path = burned
            elif not was_split:
                preserved = clips_dir / f"clip_{idx:03d}{stored_source.suffix.lower()}"
                shutil.copy2(stored_source, preserved)
                final_path = preserved

            clips.append(
                ClipInfo(
                    index=idx,
                    path=str(final_path.relative_to(run_dir)),
                    start=round(start, 3),
                    end=round(end, 3),
                    duration=round(end - start, 3),
                    subtitle_path=(str(subtitle_path.relative_to(run_dir)) if subtitle_path else None),
                )
            )

        metadata = Metadata(
            version=VERSION,
            created_at=datetime.now(timezone.utc).isoformat(),
            source_input=source,
            source_path=str(stored_source.relative_to(run_dir)),
            source_url=source_url,
            source_filename=stored_source.name,
            duration=round(duration, 3),
            segment_duration=segment_duration,
            was_split=was_split,
            speech_detected=speech_detected,
            subtitles_mode=subtitles,
            subtitles_generated=subtitles_generated,
            subtitles_skipped_reason=subtitles_skipped_reason,
            transcription_attempted=transcription_attempted,
            transcription_segments=transcription_segments,
            detected_language=detected_language,
            clips=clips,
            errors=errors,
        )
        metadata_path = run_dir / "metadata.json"
        metadata_path.write_text(json.dumps(asdict(metadata), ensure_ascii=False, indent=2), encoding="utf-8")

        print(f"✅ Готово: {run_dir}")
        return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SMM Toolkit V1.5 — URL/local video → clips + subtitles")
    parser.add_argument("source", help="URL или путь к локальному видео")
    parser.add_argument("--segment-duration", "--duration", dest="segment_duration", type=int, default=60)
    parser.add_argument("--subtitles", choices=("auto", "yes", "no"), default="auto")
    parser.add_argument("--output", default="output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        run_pipeline(args.source, args.segment_duration, args.subtitles, args.output)
        return 0
    except PipelineError as exc:
        print(f"❌ Ошибка: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n⛔ Остановлено пользователем.", file=sys.stderr)
        return 130
    except subprocess.CalledProcessError as exc:
        print(f"❌ Внешняя команда завершилась с кодом {exc.returncode}.", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
