import os
import sys
from unittest.mock import patch 

sys.path.insert(0, os.path.abspath("scripts"))

from split import split_video


@patch("split.subprocess.run")
def test_split_video_creates_expected_number_of_clips(mock_run):
    """
    Видео длительностью 125 секунд при сегментах по 60 секунд
    должно быть разделено на 3 части.
    """

    mock_run.side_effect = [
        type("Result", (), {"stdout": "125.0"})(),
        None,
        None,
        None,
    ]

    split_video("/tmp/test_video.mp4", 60)

    # 1 вызов ffprobe + 3 вызова ffmpeg
    assert mock_run.call_count == 4


@patch("split.subprocess.run")
def test_split_video_calls_ffprobe_first(mock_run):
    """
    Сначала должен выполняться ffprobe для определения длительности.
    """

    mock_run.side_effect = [
        type("Result", (), {"stdout": "120.0"})(),
        None,
        None,
    ]

    split_video("/tmp/test_video.mp4", 60)

    first_call = mock_run.call_args_list[0]

    command = first_call.args[0]

    assert command[0] == "ffprobe"
    assert "/tmp/test_video.mp4" in command


@patch("split.subprocess.run")
def test_split_video_creates_correct_number_for_exact_duration(mock_run):
    """
    Видео ровно 120 секунд при сегментах по 60 секунд
    должно дать ровно 2 части.
    """

    mock_run.side_effect = [
        type("Result", (), {"stdout": "120.0"})(),
        None,
        None,
    ]

    split_video("/tmp/test_video.mp4", 60)

    assert mock_run.call_count == 3


@patch("split.subprocess.run")
def test_split_video_creates_extra_part_for_remaining_seconds(mock_run):
    """
    61 секунда при размере сегмента 60 секунд должна дать 2 части.
    """

    mock_run.side_effect = [
        type("Result", (), {"stdout": "61.0"})(),
        None,
        None,
    ]

    split_video("/tmp/test_video.mp4", 60)

    assert mock_run.call_count == 3


@patch("split.subprocess.run")
def test_ffmpeg_commands_use_vertical_format(mock_run):
    """
    FFmpeg должен использовать вертикальный формат 1080x1920.
    """

    mock_run.side_effect = [
        type("Result", (), {"stdout": "60.0"})(),
        None,
    ]

    split_video("/tmp/test_video.mp4", 60)

    ffmpeg_call = mock_run.call_args_list[1]

    command = ffmpeg_call.args[0]

    assert command[0] == "ffmpeg"
    assert "scale=1080:1920" in command
    assert "pad=1080:1920" in command


@patch("split.subprocess.run")
def test_ffmpeg_uses_h264_and_aac(mock_run):
    """
    Проверяем кодеки, которые используются для результата.
    """

    mock_run.side_effect = [
        type("Result", (), {"stdout": "60.0"})(),
        None,
    ]

    split_video("/tmp/test_video.mp4", 60)

    command = mock_run.call_args_list[1].args[0]

    assert "libx264" in command
    assert "aac" in command
    assert "128k" in command


@patch("split.subprocess.run")
def test_ffmpeg_uses_correct_segment_start_times(mock_run):
    """
    Проверяем начало каждого сегмента.
    """

    mock_run.side_effect = [
        type("Result", (), {"stdout": "125.0"})(),
        None,
        None,
        None,
    ]

    split_video("/tmp/test_video.mp4", 60)

    ffmpeg_commands = [
        call.args[0]
        for call in mock_run.call_args_list[1:]
    ]

    assert "-ss" in ffmpeg_commands[0]
    assert "0" in ffmpeg_commands[0]

    assert "-ss" in ffmpeg_commands[1]
    assert "60" in ffmpeg_commands[1]

    assert "-ss" in ffmpeg_commands[2]
    assert "120" in ffmpeg_commands[2]


@patch("split.subprocess.run")
def test_ffmpeg_commands_use_segment_duration(mock_run):
    """
    Каждый FFmpeg сегмент должен использовать заданную длительность.
    """

    mock_run.side_effect = [
        type("Result", (), {"stdout": "125.0"})(),
        None,
        None,
        None,
    ]

    split_video("/tmp/test_video.mp4", 30)

    ffmpeg_commands = [
        call.args[0]
        for call in mock_run.call_args_list[1:]
    ]

    assert "-t" in ffmpeg_commands[0]
    assert "30" in ffmpeg_commands[0]

    assert "-t" in ffmpeg_commands[1]
    assert "30" in ffmpeg_commands[1]

    assert "-t" in ffmpeg_commands[2]
    assert "30" in ffmpeg_commands[2]

    assert "-t" in ffmpeg_commands[3]
    assert "30" in ffmpeg_commands[3]

    assert "-t" in ffmpeg_commands[4]
    assert "30" in ffmpeg_commands[4]
