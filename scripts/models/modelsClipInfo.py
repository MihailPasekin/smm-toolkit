from __future__ import annotations

from dataclasses import dataclass


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
    segment_duration: int | None
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
    output_mode: str = "video"
    quality: str = "best"
    audio_path: str | None = None
