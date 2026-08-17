import subprocess
import sys
import os
import math

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)

def split_video(video_path, segment_duration=60):
    output_dir = os.path.join(BASE_DIR, "output")
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", 
        "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", 
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    duration = float(result.stdout.strip())
    
    num_segments = math.ceil(duration / segment_duration)
    print(f"📹 {duration:.0f}с → {num_segments} клипов")
    
    for i in range(num_segments):
        start = i * segment_duration
        output_file = os.path.join(output_dir, f"{base_name}_part{i+1}.mp4")
        
        cmd = [
            "ffmpeg", "-y", "-i", video_path,
            "-ss", str(start), "-t", str(segment_duration),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,format=yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            output_file
        ]
        subprocess.run(cmd, check=True)
        print(f"✅ {output_file}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python split.py <видео> [длительность]")
        sys.exit(1)
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    split_video(sys.argv[1], duration)