import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "SmartDictate"
    app_version: str = "0.1.0"
    database_file: str = "backend/data/smartdictate.sqlite3"
    cors_allow_origins: tuple[str, ...] = (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    )


def get_settings() -> Settings:
    raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
    origins = tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())

    return Settings(
        database_file=os.getenv("SMART_DICTATE_DATABASE_FILE", Settings.database_file),
        cors_allow_origins=origins or Settings.cors_allow_origins,
    )
