import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from cut_strategy import FixedDurationCutStrategy
from subtitles import format_time, write_clip_srts
from toolkit import run_pipeline


def test_fixed_strategy_does_not_split_short_video():
    cuts = FixedDurationCutStrategy().plan(45, 60)
    assert len(cuts) == 1
    assert cuts[0].start == 0
    assert cuts[0].end == 45


def test_fixed_strategy_splits_long_video():
    cuts = FixedDurationCutStrategy().plan(125, 60)
    assert [(c.start, c.end) for c in cuts] == [(0, 60), (60, 120), (120, 125)]


def test_format_time():
    assert format_time(0) == "00:00:00,000"
    assert format_time(61.25) == "00:01:01,250"


def test_clip_subtitles_are_shifted_and_clipped(tmp_path):
    srt = tmp_path / "clip.srt"
    segments = [
        {"start": 55.0, "end": 65.0, "text": "hello"},
        {"start": 70.0, "end": 75.0, "text": "world"},
    ]
    write_clip_srts(segments, 60, 72, srt)
    text = srt.read_text(encoding="utf8")
    assert "00:00:00,000 --> 00:00:05,000" in text
    assert "hello" in text
    assert "00:00:10,000 --> 00:00:12,000" in text
    assert "world" in text


@patch("toolkit.has_speech", return_value=False)
@patch("toolkit.transcribe_to_srt")
@patch("toolkit.probe_duration", return_value=40.0)
@patch("toolkit.has_audio", return_value=True)
def test_auto_skips_whisper_when_no_speech(
    mock_audio, mock_duration, mock_transcribe, mock_speech, tmp_path
):
    video = tmp_path / "silent.mp4"
    video.write_bytes(b"fake")

    out = run_pipeline(str(video), subtitles="auto", output_root=tmp_path / "out")

    mock_speech.assert_called_once()
    mock_transcribe.assert_not_called()
    metadata = json.loads((out / "metadata.json").read_text(encoding="utf8"))
    assert metadata["speech_detected"] is False
    assert metadata["subtitles_generated"] is False


@patch("toolkit.has_speech", return_value=True)
@patch("toolkit.transcribe_to_srt", return_value={
    "language": "ru",
    "segments": [{"start": 0, "end": 40, "text": "test"}],
    "path": "source.srt",
    "generated": True,
    "reason": None,
})
@patch("toolkit.burn_subtitles", side_effect=lambda video, srt, out: Path(out).write_bytes(b"burned"))
@patch("toolkit.probe_duration", return_value=125.0)
@patch("toolkit.has_audio", return_value=True)
@patch("toolkit.render_cuts", return_value=[])
def test_long_video_gets_per_clip_subtitles(
    mock_render, mock_audio, mock_duration, mock_burn, mock_transcribe, mock_speech, tmp_path
):
    video = tmp_path / "long.mp4"
    video.write_bytes(b"fake")

    # Simulate the renderer output without invoking ffmpeg.
    def render(_source, clips_dir, cuts):
        result = []
        for i, cut in enumerate(cuts, 1):
            p = Path(clips_dir) / f"clip_{i:03d}.mp4"
            p.write_bytes(b"clip")
            result.append((p, cut.start, cut.end))
        return result

    mock_render.side_effect = render

    out = run_pipeline(str(video), subtitles="auto", output_root=tmp_path / "out")

    assert mock_transcribe.called
    assert mock_burn.call_count == 3
    metadata = json.loads((out / "metadata.json").read_text(encoding="utf8"))
    assert metadata["was_split"] is True
    assert len(metadata["clips"]) == 3


def test_no_subtitles_never_runs_vad_or_whisper(tmp_path):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake")

    with patch("toolkit.has_audio") as audio, \
         patch("toolkit.has_speech") as speech, \
         patch("toolkit.transcribe_to_srt") as transcribe, \
         patch("toolkit.probe_duration", return_value=20.0):
        run_pipeline(str(video), subtitles="no", output_root=tmp_path / "out")
        audio.assert_not_called()
        speech.assert_not_called()
        transcribe.assert_not_called()


def test_cli_accepts_subtitle_modes():
    from toolkit import build_parser
    parser = build_parser()
    assert parser.parse_args(["video.mp4", "--subtitles", "auto"]).subtitles == "auto"
    assert parser.parse_args(["video.mp4", "--subtitles", "yes"]).subtitles == "yes"
    assert parser.parse_args(["video.mp4", "--subtitles", "no"]).subtitles == "no"


@patch("toolkit.has_speech", return_value=True)
@patch("toolkit.transcribe_to_srt", return_value={
    "language": "en",
    "segments": [],
    "path": None,
    "generated": False,
    "reason": "whisper_no_segments",
})
@patch("toolkit.probe_duration", return_value=9.4)
@patch("toolkit.has_audio", return_value=True)
def test_auto_falls_back_to_plain_video_when_whisper_finds_no_segments(
    mock_audio, mock_duration, mock_transcribe, mock_speech, tmp_path
):
    video = tmp_path / "speech_like.mp4"
    video.write_bytes(b"fake")

    out = run_pipeline(
        str(video),
        subtitles="auto",
        output_root=tmp_path / "out",
    )

    assert mock_transcribe.called
    assert (out / "clips" / "clip_001.mp4").exists()
    assert not (out / "subtitles" / "source.srt").exists()
    assert not (out / "subtitles" / "clip_001.srt").exists()

    metadata = json.loads((out / "metadata.json").read_text(encoding="utf8"))
    assert metadata["speech_detected"] is True
    assert metadata["transcription_attempted"] is True
    assert metadata["transcription_segments"] == 0
    assert metadata["subtitles_generated"] is False
    assert metadata["subtitles_skipped_reason"] == "whisper_no_segments"


@patch("toolkit.has_speech", return_value=True)
@patch("toolkit.transcribe_to_srt", return_value={
    "language": "en",
    "segments": [],
    "path": None,
    "generated": False,
    "reason": "whisper_no_segments",
})
@patch("toolkit.probe_duration", return_value=9.4)
@patch("toolkit.has_audio", return_value=True)
def test_yes_fails_cleanly_when_whisper_finds_no_segments(
    mock_audio, mock_duration, mock_transcribe, mock_speech, tmp_path
):
    video = tmp_path / "speech_like.mp4"
    video.write_bytes(b"fake")

    from toolkit import PipelineError

    try:
        run_pipeline(
            str(video),
            subtitles="yes",
            output_root=tmp_path / "out",
        )
    except PipelineError as exc:
        assert "Whisper не обнаружил" in str(exc)
    else:
        raise AssertionError("Expected PipelineError")
