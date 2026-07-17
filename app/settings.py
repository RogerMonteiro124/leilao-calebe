# -*- coding: utf-8 -*-
import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env")


class Settings:
    event_name: str = os.getenv("EVENT_NAME", "Leilão Calebe")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin")
    admin_password: str = os.getenv("ADMIN_PASSWORD", "senha-forte")
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'leilao.db'}")
    upload_max_bytes: int = int(os.getenv("UPLOAD_MAX_BYTES", "5242880"))
    upload_dir: Path = BASE_DIR / "static" / "uploads"


settings = Settings()