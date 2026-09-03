# scripts/subtitles.py
from __future__ import annotations

import warnings
import subprocess
from pathlib import Path


def format_time(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    total_ms = round(seconds * 1000)
    hrs, rem = divmod(total_ms, 3_600_000)
    mins, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"


def transcribe_to_srt(video_path: str | Path, output_srt: str | Path) -> dict:
    """Транскрипция с оптимизацией для Mac M4"""
    video_path = Path(video_path)
    output_srt = Path(output_srt)
    output_srt.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"🎤 Распознаю речь: {video_path}")
    
    # Пытаемся использовать mlx-whisper (самый быстрый на Mac M4)
    try:
        import mlx_whisper
        print("⚡ Использую mlx-whisper (оптимизировано для Apple Silicon)")
        
        result = mlx_whisper.transcribe(
            str(video_path),
            path_or_hf_repo="mlx-community/whisper-small",  # small быстрее чем base
            verbose=False,
            word_timestamps=False,
            temperature=0.0,
            compression_ratio_threshold=2.4,
            logprob_threshold=-1.0,
            no_speech_threshold=0.6,
            condition_on_previous_text=True,
            initial_prompt=None,
        )
        
        segments = result.get("segments", [])
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
        
    except ImportError:
        print("⚠️  mlx-whisper не установлен, пробую faster-whisper...")
        
        # Пытаемся использовать faster-whisper
        try:
            from faster_whisper import WhisperModel
            print("⚡ Использую faster-whisper с оптимизацией для Mac M4")
            
            # Используем модель small с оптимизацией для CPU
            model = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=8)
            
            segments, info = model.transcribe(
                str(video_path),
                beam_size=5,
                language=None,
                condition_on_previous_text=True,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    threshold=0.5,
                ),
            )
            
            segments_list = []
            for segment in segments:
                segments_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip(),
                })
            
            if not segments_list:
                output_srt.unlink(missing_ok=True)
                return {
                    "language": info.language,
                    "segments": [],
                    "path": None,
                    "generated": False,
                    "reason": "whisper_no_segments",
                }
            
            _write_segments(segments_list, 0.0, float("inf"), output_srt)
            
            return {
                "language": info.language,
                "segments": segments_list,
                "path": str(output_srt),
                "generated": output_srt.exists() and output_srt.stat().st_size > 0,
                "reason": None,
            }
            
        except ImportError:
            print("⚠️  faster-whisper не установлен, использую обычный whisper...")
            
            # Падаем на обычный whisper
            warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")
            import whisper
            
            print("🐢 Использую обычный whisper (медленнее, но работает)")
            model = whisper.load_model("small", device="cpu")  # small вместо base
            result = model.transcribe(str(video_path), fp16=False, verbose=False)
            
            segments = [
                segment for segment in result.get("segments", [])
                if segment.get("text", "").strip()
            ]
            
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
    
    except Exception as e:
        print(f"❌ Ошибка транскрипции: {e}")
        output_srt.unlink(missing_ok=True)
        return {
            "language": "unknown",
            "segments": [],
            "path": None,
            "generated": False,
            "reason": f"transcription_error: {str(e)}",
        }


def _write_segments(segments, clip_start: float, clip_end: float, output_srt: Path) -> None:
    lines = []
    number = 1
    
    for segment in segments:
        # Поддержка разных форматов данных
        if isinstance(segment, dict):
            seg_start = float(segment.get("start", 0))
            seg_end = float(segment.get("end", 0))
            text = segment.get("text", "").strip()
        else:
            # Для faster-whisper объекты
            seg_start = float(segment["start"] if isinstance(segment, dict) else segment.start)
            seg_end = float(segment["end"] if isinstance(segment, dict) else segment.end)
            text = segment.get("text", "").strip() if isinstance(segment, dict) else segment.text.strip()
        
        overlap_start = max(seg_start, clip_start)
        overlap_end = min(seg_end, clip_end)
        
        if overlap_end <= overlap_start:
            continue
        
        local_start = overlap_start - clip_start
        local_end = overlap_end - clip_start
        
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
def validate_srt(srt_path: Path, duration: float):
    """Validate SRT file."""
    if not srt_path.exists():
        from errors import ValidationError
        raise ValidationError("SRT file does not exist")
