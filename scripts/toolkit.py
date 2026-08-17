import sys
import os
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

def run_script(name, *args):
    script_path = os.path.join(SCRIPT_DIR, name)
    cmd = [sys.executable, script_path] + list(args)
    subprocess.run(cmd, check=True)

def process_video(video_path, segment_duration=60):
    # Превращаем в абсолютный путь
    video_path = os.path.abspath(video_path)
    print(f"🚀 Обработка: {video_path}")
    
    print("🎤 Шаг 1: Создаю субтитры...")
    run_script("subtitles.py", video_path)
    
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    srt_path = os.path.join(BASE_DIR, "output", f"{base_name}.srt")
    
    print("✂️ Шаг 2: Нарезка на клипы...", run_script)
    run_script("split.py", video_path, str(segment_duration))
    
    print("📝 Шаг 3: Наложение субтитров...")
    for i in range(1, 50):
        part = os.path.join(BASE_DIR, "output", f"{base_name}_part{i}.mp4")
        if not os.path.exists(part):
            break
        run_script("burn_subs.py", part, srt_path)
        os.remove(part)
    
    print("✅ Готово! Смотри папку output/")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python toolkit.py <путь_к_видео> [длительность]")
        sys.exit(1)
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    process_video(sys.argv[1], duration)