import subprocess
from pathlib import Path

import pytest

from validator import ValidationError, validate_srt, validate_video


def test_validate_video_rejects_missing_file(tmp_path):
    with pytest.raises(ValidationError):
        validate_video(tmp_path / "missing.mp4")


def test_validate_video_rejects_empty_file(tmp_path):
    video = tmp_path / "empty.mp4"
    video.write_bytes(b"")

    with pytest.raises(ValidationError):
        validate_video(video)


def test_validate_srt_rejects_empty_file(tmp_path):
    srt = tmp_path / "empty.srt"
    srt.write_text("", encoding="utf-8")

    with pytest.raises(ValidationError):
        validate_srt(srt)


def test_validate_srt_accepts_valid_file(tmp_path):
    srt = tmp_path / "valid.srt"

    srt.write_text(
        """1
00:00:00,000 --> 00:00:02,000
Hello

2
00:00:02,000 --> 00:00:04,000
World
""",
        encoding="utf-8",
    )

    assert validate_srt(srt, duration=5.0) == 2


def test_validate_srt_rejects_invalid_timestamp(tmp_path):
    srt = tmp_path / "invalid.srt"

    srt.write_text(
        """1
00:00:04,000 --> 00:00:02,000
Broken
""",
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        validate_srt(srt)