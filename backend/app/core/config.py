import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "SmartDictate"
    app_version: str = "0.1.0"
    data_file: str = "backend/data/transcripts.json"
    hotword_file: str = "backend/data/hotwords.json"
    cors_allow_origins: tuple[str, ...] = (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    )


def get_settings() -> Settings:
    raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
    origins = tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())

    return Settings(
        data_file=os.getenv("SMART_DICTATE_DATA_FILE", Settings.data_file),
        hotword_file=os.getenv("SMART_DICTATE_HOTWORD_FILE", Settings.hotword_file),
        cors_allow_origins=origins or Settings.cors_allow_origins,
    )
