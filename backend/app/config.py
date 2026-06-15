"""
Global application configuration — loaded from environment variables via pydantic-settings.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "sqlite+aiosqlite:////app/data/db/photos.db"

    # Directories
    photos_root: str = "/photos"
    thumbnails_dir: str = "/app/data/thumbnails"
    # Imported photos land inside the real library under a dedicated app folder,
    # so they are scanned and browsed together with the rest of the library.
    # Requires the /photos mount to be read-write.
    import_dir: str = "/photos/PicJournal"

    # Supported image extensions
    supported_extensions: tuple[str, ...] = (
        ".jpg", ".jpeg", ".png", ".heic", ".heif",
        ".webp", ".tiff", ".tif", ".bmp", ".raw",
        ".cr2", ".nef", ".arw", ".dng",
    )

    # Supported video extensions
    video_extensions: tuple[str, ...] = (
        ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".hevc", ".webm",
    )

    # FFmpeg concurrency limit — protect NAS CPU from saturation
    ffmpeg_max_concurrent: int = 1

    # Concurrency
    worker_processes: int = 4

    # Thumbnail sizes (px, short edge)
    thumbnail_sizes: tuple[int, ...] = (256, 1080)

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # pHash similarity threshold (hamming distance)
    phash_threshold: int = 10

    # Burst shot detection: max seconds between shots in same group
    burst_interval_seconds: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
