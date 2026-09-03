
# scripts/youtube_api.py
import requests
import re
from pathlib import Path
from typing import Optional, Dict, Any

# Убираем точку — импортируем напрямую
from errors import PipelineError

class YouTubeAPI:
    """Класс для работы с YouTube Data API v3"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"
    
    def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """Получить информацию о видео по ID."""
        url = f"{self.base_url}/videos"
        params = {
            "part": "snippet,contentDetails,statistics",
            "id": video_id,
            "key": self.api_key
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("items"):
                raise PipelineError(f"Видео с ID {video_id} не найдено")
            
            item = data["items"][0]
            return {
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "channel_name": item["snippet"]["channelTitle"],
                "duration": self._parse_duration(item["contentDetails"]["duration"]),
                "view_count": int(item["statistics"].get("viewCount", 0)),
                "like_count": int(item["statistics"].get("likeCount", 0)),
                "comment_count": int(item["statistics"].get("commentCount", 0)),
                "thumbnail": item["snippet"]["thumbnails"]["high"]["url"],
                "published_at": item["snippet"]["publishedAt"],
            }
        except requests.RequestException as exc:
            raise PipelineError(f"Ошибка при запросе к YouTube API: {exc}") from exc
    
    @staticmethod
    def _parse_duration(duration: str) -> int:
        """Парсит длительность из ISO 8601 формата в секунды."""
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if not match:
            return 0
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        seconds = int(match.group(3) or 0)
        return hours * 3600 + minutes * 60 + seconds


def extract_video_id(url: str) -> Optional[str]:
    """Извлечь ID видео из URL."""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})(?:[?&]|$)',
        r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None
