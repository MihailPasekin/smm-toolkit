import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from cut_strategy import FixedDurationCutStrategy
from subtitles import format_time, write_clip_srts
from toolkit import build_parser, build_video_format_selector, run_pipeline
from validator import VideoInfo


def _video_info(duration, **overrides):
    defaults = dict(
        path=Path("fake.mp4"),
        duration=duration,
        video_codec="h264",
        audio_codec="aac",
        width=1280,
        height=720,
        fps=30.0,
        has_audio=True,
    )
    defaults.update(overrides)
    return VideoInfo(**defaults)


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
@patch("toolkit.validate_video", return_value=_video_info(40.0))
@patch("toolkit.has_audio", return_value=True)
def test_auto_skips_whisper_when_no_speech(
    mock_audio, mock_validate, mock_transcribe, mock_speech, tmp_path
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
    "segments": [
        {"start": 0, "end": 40, "text": "one"},
        {"start": 65, "end": 100, "text": "two"},
        {"start": 121, "end": 124, "text": "three"},
    ],
    "path": "source.srt",
    "generated": True,
    "reason": None,
})
@patch("toolkit.burn_subtitles", side_effect=lambda video, srt, out: Path(out).write_bytes(b"burned"))
@patch("toolkit.validate_video")
@patch("toolkit.has_audio", return_value=True)
@patch("toolkit.render_cuts", return_value=[])
def test_long_video_gets_per_clip_subtitles(
    mock_render, mock_audio, mock_validate, mock_burn, mock_transcribe, mock_speech, tmp_path
):
    video = tmp_path / "long.mp4"
    video.write_bytes(b"fake")

    clip_durations = {}

    # Simulate the renderer output without invoking ffmpeg.
    def render(_source, clips_dir, cuts):
        result = []
        for i, cut in enumerate(cuts, 1):
            p = Path(clips_dir) / f"clip_{i:03d}.mp4"
            p.write_bytes(b"clip")
            clip_durations[str(p)] = cut.end - cut.start
            result.append((p, cut.start, cut.end))
        return result

    mock_render.side_effect = render
    mock_validate.side_effect = lambda path: _video_info(
        clip_durations.get(str(Path(path)), 125.0)
    )

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
         patch("toolkit.validate_video", return_value=_video_info(20.0)):
        run_pipeline(str(video), subtitles="no", output_root=tmp_path / "out")
        audio.assert_not_called()
        speech.assert_not_called()
        transcribe.assert_not_called()


def test_cli_accepts_subtitle_modes():
    parser = build_parser()
    assert parser.parse_args(["video.mp4", "--subtitles", "auto"]).subtitles == "auto"
    assert parser.parse_args(["video.mp4", "--subtitles", "yes"]).subtitles == "yes"
    assert parser.parse_args(["video.mp4", "--subtitles", "no"]).subtitles == "no"


def test_cli_accepts_output_mode_quality_and_no_split():
    parser = build_parser()
    args = parser.parse_args(
        [
            "https://example.com/video",
            "--mode",
            "subtitled",
            "--quality",
            "720",
            "--no-split",
        ]
    )

    assert args.mode == "subtitled"
    assert args.quality == "720"
    assert args.no_split is True


def test_cli_source_is_optional_for_interactive_mode():
    args = build_parser().parse_args([])

    assert args.source is None


def test_quality_selector_limits_requested_height_and_prefers_hls():
    selector = build_video_format_selector("720")

    assert "[height<=720]" in selector
    assert "[protocol^=m3u8]" in selector
    assert selector.count("[height<=720]") == 3


def test_interactive_dialog_collects_subtitled_video_options():
    from interactive import prompt_for_options

    answers = iter([
        "https://example.com/video",
        "2",  # video with subtitles
        "3",  # 720p
        "1",  # split into 60-second clips
    ])

    options = prompt_for_options(input_func=lambda _prompt: next(answers))

    assert options.source == "https://example.com/video"
    assert options.mode == "subtitled"
    assert options.quality == "720"
    assert options.segment_duration == 60


def test_interactive_dialog_skips_quality_and_cut_for_audio():
    from interactive import prompt_for_options

    answers = iter(["https://example.com/video", "3"])

    options = prompt_for_options(input_func=lambda _prompt: next(answers))

    assert options.mode == "audio"
    assert options.quality == "best"
    assert options.segment_duration is None


@patch("toolkit.download_video")
@patch("toolkit.validate_video", return_value=_video_info(125.0))
def test_pipeline_passes_quality_to_url_download_and_can_skip_cutting(
    mock_validate, mock_download, tmp_path
):
    downloaded = tmp_path / "source.mp4"
    downloaded.write_bytes(b"fake")
    mock_download.return_value = downloaded

    out = run_pipeline(
        "https://example.com/video",
        segment_duration=None,
        subtitles="no",
        quality="720",
        output_root=tmp_path / "out",
    )

    assert mock_download.call_args.args[0] == "https://example.com/video"
    assert mock_download.call_args.args[2] == "720"
    metadata = json.loads((out / "metadata.json").read_text(encoding="utf8"))
    assert metadata["was_split"] is False
    assert metadata["quality"] == "720"


@patch("toolkit.extract_audio", side_effect=lambda _source, target: Path(target).write_bytes(b"mp3"))
@patch("toolkit.validate_video", return_value=_video_info(20.0))
@patch("toolkit.transcribe_to_srt")
@patch("toolkit.has_speech")
def test_audio_mode_exports_mp3_and_skips_subtitles_and_cutting(
    mock_speech, mock_transcribe, mock_validate, mock_extract_audio, tmp_path
):
    video = tmp_path / "video.mp4"
    video.write_bytes(b"fake")

    out = run_pipeline(
        str(video),
        output_mode="audio",
        output_root=tmp_path / "out",
    )

    assert (out / "audio" / "video.mp3").read_bytes() == b"mp3"
    mock_extract_audio.assert_called_once()
    mock_speech.assert_not_called()
    mock_transcribe.assert_not_called()
    metadata = json.loads((out / "metadata.json").read_text(encoding="utf8"))
    assert metadata["output_mode"] == "audio"
    assert metadata["audio_path"] == "audio/video.mp3"
    assert metadata["clips"] == []


@patch("toolkit.download_audio")
@patch("toolkit.probe_duration", return_value=20.0)
@patch("toolkit.validate_video")
def test_audio_mode_downloads_mp3_directly_from_url(
    mock_validate, mock_duration, mock_download, tmp_path
):
    downloaded = tmp_path / "source.mp3"
    downloaded.write_bytes(b"mp3")
    mock_download.return_value = downloaded

    out = run_pipeline(
        "https://example.com/video",
        output_mode="audio",
        output_root=tmp_path / "out",
    )

    mock_download.assert_called_once()
    mock_validate.assert_not_called()
    assert (out / "audio" / "source.mp3").read_bytes() == b"mp3"


@patch("toolkit.run_pipeline")
@patch("toolkit.prompt_for_options")
def test_main_uses_interactive_options_when_source_is_not_provided(
    mock_prompt, mock_pipeline, monkeypatch
):
    from interactive import UserOptions
    from toolkit import main

    mock_prompt.return_value = UserOptions(
        source="https://example.com/video",
        mode="subtitled",
        quality="720",
        segment_duration=None,
    )
    monkeypatch.setattr(sys, "argv", ["toolkit.py"])

    assert main() == 0
    mock_pipeline.assert_called_once_with(
        "https://example.com/video",
        segment_duration=None,
        subtitles="auto",
        output_root="output",
        quality="720",
        output_mode="subtitled",
    )


@patch("toolkit.has_speech", return_value=True)
@patch("toolkit.transcribe_to_srt", return_value={
    "language": "en",
    "segments": [],
    "path": None,
    "generated": False,
    "reason": "whisper_no_segments",
})
@patch("toolkit.validate_video", return_value=_video_info(9.4))
@patch("toolkit.has_audio", return_value=True)
def test_auto_falls_back_to_plain_video_when_whisper_finds_no_segments(
    mock_audio, mock_validate, mock_transcribe, mock_speech, tmp_path
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
@patch("toolkit.validate_video", return_value=_video_info(9.4))
@patch("toolkit.has_audio", return_value=True)
def test_yes_fails_cleanly_when_whisper_finds_no_segments(
    mock_audio, mock_validate, mock_transcribe, mock_speech, tmp_path
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
