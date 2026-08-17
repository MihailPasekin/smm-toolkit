import whisper
import sys
import os
import warnings

warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

def generate_subtitles(video_path):
    output_dir = os.path.join(BASE_DIR, "output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Без device="mps" — работает на CPU, стабильно
    model = whisper.load_model("base")
    
    print(f"🎤 Распознаю речь: {video_path}")
    # Автоопределение языка — без language="ru"
    result = model.transcribe(video_path)
    
    detected = result.get("language", "unknown")
    print(f"🌍 Определён язык: {detected}")
    
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    srt_path = os.path.join(output_dir, f"{base_name}.srt")
    
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(result["segments"], 1):
            start = format_time(segment["start"])
            end = format_time(segment["end"])
            text = segment["text"].strip()
            f.write(f"{i}\n{start} --> {end}\n{text}\n\n")
    
    print(f"✅ Субтитры: {srt_path}")
    return srt_path

def format_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{ms:03d}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python subtitles.py <путь_к_видео>")
        sys.exit(1)
    generate_subtitles(sys.argv[1])