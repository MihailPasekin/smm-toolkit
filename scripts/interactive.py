# scripts/interactive.py
from dataclasses import dataclass
from config import QUALITY_CHOICES

@dataclass
class Options:
    source: str
    segment_duration: int
    mode: str
    quality: str

def prompt_for_options() -> Options:
    source = input("Enter video URL or file path: ").strip()
    if not source:
        source = input("Enter video URL or file path: ").strip()
    
    print("\nWhat to download?")
    print("  1. Video only")
    print("  2. Video with subtitles")
    print("  3. Audio only (MP3)")
    mode_choice = input("Choose option: ").strip()
    
    mode_map = {"1": "video", "2": "subtitled", "3": "audio"}
    mode = mode_map.get(mode_choice, "video")
    
    print("\nWhat video quality?")
    print("  1. Best available")
    print("  2. 1080p or lower")
    print("  3. 720p or lower")
    print("  4. 480p or lower")
    print("  5. 360p or lower")
    quality_choice = input("Choose option: ").strip()
    
    quality_map = {"1": "best", "2": "1080", "3": "720", "4": "480", "5": "360"}
    quality = quality_map.get(quality_choice, "best")
    
    print("\nSplit video into clips of 60 seconds?")
    print("  1. Yes")
    print("  2. No")
    split_choice = input("Choose option: ").strip()
    
    segment_duration = 60 if split_choice == "1" else None
    
    return Options(source, segment_duration, mode, quality)
