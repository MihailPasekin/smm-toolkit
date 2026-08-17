import subprocess
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

def burn_subtitles(video_path, srt_path):
    output_dir = os.path.join(BASE_DIR, "output")
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_file = os.path.join(output_dir, f"{base_name}_subtitled.mp4")
    
    subtitle_filter = (
        f"subtitles={srt_path}:force_style='"
        "FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,Outline=2,Alignment=2'"
    )
    
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", subtitle_filter,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy",
        output_file
    ]
    subprocess.run(cmd, check=True)
    print(f"✅ Субтитры наложены: {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Использование: python burn_subs.py <видео> <субтитры.srt>")
        sys.exit(1)
    burn_subtitles(sys.argv[1], sys.argv[2])