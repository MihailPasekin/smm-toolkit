# scripts/models/modelsClipInfo.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class ClipInfo:
    index: int
    path: str
    start: float
    end: float
    duration: float
    subtitle_path: Optional[str] = None


@dataclass
class Metadata:
    version: str
    created_at: str
    source_input: str
    source_path: str
    source_url: Optional[str]
    source_filename: str
    duration: float
    segment_duration: Optional[int]
    was_split: bool
    speech_detected: bool
    subtitles_mode: str
    subtitles_generated: bool
    subtitles_skipped_reason: Optional[str]
    transcription_attempted: bool
    transcription_segments: int
    detected_language: Optional[str]
    clips: List[ClipInfo]
    errors: List[str]
    output_mode: str
    quality: str
    audio_path: Optional[str] = None
