from __future__ import annotations

import subprocess
from pathlib import Path

try:
    import webrtcvad
except ImportError:
    webrtcvad = None


def has_speech(video_path: str | Path, sample_rate: int = 16000,
               frame_ms: int = 30, min_speech_seconds: float = 0.5) -> bool:
    """Fast VAD gate. Whisper is intentionally not imported here."""
    if webrtcvad is None:
        raise RuntimeError("webrtcvad не установлен. Выполните pip install -r requirements.txt")

    bytes_per_frame = int(sample_rate * frame_ms / 1000) * 2
    cmd = [
        "ffmpeg", "-v", "error", "-i", str(video_path),
        "-vn", "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-",
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError as exc:
        raise RuntimeError("Не найден ffmpeg. Установите его: brew install ffmpeg") from exc

    vad = webrtcvad.Vad(2)
    voiced_seconds = 0.0
    buffer = b""
    assert proc.stdout is not None
    while True:
        chunk = proc.stdout.read(bytes_per_frame * 32)
        if not chunk:
            break
        buffer += chunk
        while len(buffer) >= bytes_per_frame:
            frame, buffer = buffer[:bytes_per_frame], buffer[bytes_per_frame:]
            if vad.is_speech(frame, sample_rate):
                voiced_seconds += frame_ms / 1000
                if voiced_seconds >= min_speech_seconds:
                    proc.kill()
                    proc.wait()
                    return True

    stderr = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
    code = proc.wait()
    if code != 0:
        raise RuntimeError(f"ffmpeg VAD завершился с кодом {code}: {stderr.strip()[-1000:]}")
    return False
