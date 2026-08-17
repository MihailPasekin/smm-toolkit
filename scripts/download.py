import sys
import os
import subprocess

def download_video(url, output_dir="input"):
    os.makedirs(output_dir, exist_ok=True)
    # Скачиваем лучшее качество
    cmd = [
        "yt-dlp",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", f"{output_dir}/%(title)s.%(ext)s",
        url
    ]
    subprocess.run(cmd, check=True)
    print("✅ Видео скачано в папку input/")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python scripts/download.py <URL>")
        sys.exit(1)
    download_video(sys.argv[1])



    