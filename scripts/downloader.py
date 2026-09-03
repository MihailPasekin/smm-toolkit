import subprocess
import sys
from pathlib import Path

def download_with_ytdlp_modern(url: str, output_dir: str | Path) -> Path | None:
    """Скачивание через yt-dlp с современными параметрами для YouTube"""
    try:
        import yt_dlp
        print("📥 Пробую yt-dlp с современными параметрами...")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Современные параметры для YouTube
        ydl_opts = {
            'outtmpl': str(output_dir / '%(title)s.%(ext)s'),
            'format': 'bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'mweb'],
                    'skip': ['hls', 'dash'],
                    'formats': ['missing_pot'],
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                filename = ydl.prepare_filename(info)
                if Path(filename).exists():
                    print(f"✅ yt-dlp скачал: {filename}")
                    return Path(filename)
    except Exception as e:
        print(f"⚠️ yt-dlp с современными параметрами не сработал: {e}")
    return None

def download_with_pytube(url: str, output_dir: str | Path) -> Path | None:
    """Попытка скачать через pytube (только YouTube)"""
    try:
        from pytube import YouTube
        print("📥 Пробую pytube...")
        yt = YouTube(url)
        video = yt.streams.get_highest_resolution()
        if video:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            path = video.download(output_path=str(output_dir))
            print(f"✅ pytube скачал: {path}")
            return Path(path)
    except Exception as e:
        print(f"⚠️ pytube не сработал: {e}")
    return None

def download_with_instaloader(url: str, output_dir: str | Path) -> Path | None:
    """Попытка скачать через instaloader (только Instagram)"""
    try:
        import instaloader
        print("📥 Пробую instaloader...")
        loader = instaloader.Instaloader()
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        import os
        old_cwd = os.getcwd()
        os.chdir(str(output_dir))
        loader.download_post(url, target="")
        os.chdir(old_cwd)
        
        files = list(output_dir.glob("*.mp4"))
        if files:
            print(f"✅ instaloader скачал: {files[0]}")
            return files[0]
    except Exception as e:
        print(f"⚠️ instaloader не сработал: {e}")
    return None

def download_with_ytdlp_fallback(url: str, output_dir: str | Path) -> Path | None:
    """Попытка скачать через yt-dlp с обходными параметрами"""
    try:
        import yt_dlp
        print("📥 Пробую yt-dlp с обходными параметрами...")
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Используем параметры для обхода блокировки YouTube
        ydl_opts = {
            'outtmpl': str(output_dir / '%(title)s.%(ext)s'),
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'tv_embedded'],
                    'skip': ['hls', 'dash'],
                }
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                filename = ydl.prepare_filename(info)
                if Path(filename).exists():
                    print(f"✅ yt-dlp (обход) скачал: {filename}")
                    return Path(filename)
    except Exception as e:
        print(f"⚠️ yt-dlp обходной не сработал: {e}")
    return None

def download_video_smart(url: str, output_dir: str | Path) -> Path:
    """Умная загрузка: пробует разные способы"""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"⬇️ Скачивание: {url}")
    
    is_youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()
    is_instagram = "instagram.com" in url.lower()
    
    # Для YouTube: пробуем все методы
    if is_youtube:
        # 1. Современный yt-dlp (с новыми параметрами)
        result = download_with_ytdlp_modern(url, output_dir)
        if result:
            return result
        
        # 2. pytube
        result = download_with_pytube(url, output_dir)
        if result:
            return result
        
        # 3. Обходной yt-dlp
        result = download_with_ytdlp_fallback(url, output_dir)
        if result:
            return result
    
    # Для Instagram: instaloader или yt-dlp
    if is_instagram:
        result = download_with_instaloader(url, output_dir)
        if result:
            return result
    
    # Универсальные методы
    result = download_with_ytdlp_modern(url, output_dir)
    if result:
        return result
    
    result = download_with_ytdlp_fallback(url, output_dir)
    if result:
        return result
    
    raise Exception(f"❌ Не удалось скачать видео ни одним из способов: {url}")