import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - keeps startup usable before dependency install.
    load_dotenv = None


@dataclass(frozen=True)
class Settings:
    app_name: str = "SmartDictate"
    app_version: str = "0.1.0"
    database_file: str = "backend/data/smartdictate.sqlite3"
    upload_dir: str = "backend/data/uploads"
    xfyun_app_id: str = ""
    xfyun_api_key: str = ""
    xfyun_api_secret: str = ""
    xfyun_request_timeout: int = 45
    xfyun_file_poll_interval: int = 5
    xfyun_file_max_polls: int = 24
    cors_allow_origins: tuple[str, ...] = (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    )


def get_settings() -> Settings:
    if load_dotenv:
        load_dotenv()

    raw_origins = os.getenv("CORS_ALLOW_ORIGINS", "")
    origins = tuple(origin.strip() for origin in raw_origins.split(",") if origin.strip())

    return Settings(
        database_file=os.getenv("SMART_DICTATE_DATABASE_FILE", Settings.database_file),
        upload_dir=os.getenv("SMART_DICTATE_UPLOAD_DIR", Settings.upload_dir),
        xfyun_app_id=os.getenv("XFYUN_APP_ID") or os.getenv("APP_ID", ""),
        xfyun_api_key=os.getenv("XFYUN_API_KEY") or os.getenv("API_KEY", ""),
        xfyun_api_secret=os.getenv("XFYUN_API_SECRET") or os.getenv("API_SECRET", ""),
        xfyun_request_timeout=int(
            os.getenv("XFYUN_REQUEST_TIMEOUT", str(Settings.xfyun_request_timeout))
        ),
        xfyun_file_poll_interval=int(
            os.getenv("XFYUN_FILE_POLL_INTERVAL", str(Settings.xfyun_file_poll_interval))
        ),
        xfyun_file_max_polls=int(
            os.getenv("XFYUN_FILE_MAX_POLLS", str(Settings.xfyun_file_max_polls))
        ),
        cors_allow_origins=origins or Settings.cors_allow_origins,
    )
