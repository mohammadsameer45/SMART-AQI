"""
Central configuration for the SMART AQI backend.

All values come from environment variables (loaded from backend/.env in
development via python-dotenv). Nothing secret is hard-coded here and none of
these values are ever sent to the frontend.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent

# Load backend/.env if present (no-op in production where real env vars are set)
load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    # --- database ---
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB: str = os.getenv("MONGO_DB", "smart_aqi")

    # --- auth ---
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_HOURS: int = int(os.getenv("JWT_EXPIRES_HOURS", "24"))
    BCRYPT_ROUNDS: int = int(os.getenv("BCRYPT_ROUNDS", "12"))

    # --- app ---
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    DEBUG: bool = _bool("FLASK_DEBUG", "true")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    API_PREFIX: str = "/api"

    # --- external data services (used by offline pipelines, never the browser) ---
    DATA_GOV_IN_API_KEY: str = os.getenv("DATA_GOV_IN_API_KEY", "")
    DATA_GOV_IN_AQI_RESOURCE: str = os.getenv(
        "DATA_GOV_IN_AQI_RESOURCE", "3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69")
    OPEN_METEO_BASE: str = os.getenv("OPEN_METEO_BASE",
                                     "https://api.open-meteo.com")
    # scripts/refresh_worker.py re-pulls the CPCB live feed on this interval
    LIVE_REFRESH_MINUTES: int = int(os.getenv("LIVE_REFRESH_MINUTES", "45"))

    # --- web push (threshold alerts) ---
    VAPID_PRIVATE_KEY_PEM: str = os.getenv("VAPID_PRIVATE_KEY_PEM", "").replace("\\n", "\n")
    VAPID_PUBLIC_KEY: str = os.getenv("VAPID_PUBLIC_KEY", "")
    VAPID_SUBJECT: str = os.getenv("VAPID_SUBJECT", "")

    # --- paths ---
    DATA_DIR: Path = PROJECT_ROOT / "data"
    CLEANED_DIR: Path = DATA_DIR / "cleaned"
    METADATA_DIR: Path = DATA_DIR / "metadata"
    ML_MODELS_DIR: Path = BACKEND_DIR / "ml_models"

    @classmethod
    def validate(cls, require_secrets: bool = True) -> None:
        missing = []
        if require_secrets and not cls.JWT_SECRET:
            missing.append("JWT_SECRET")
        if missing:
            raise RuntimeError(
                "Missing required environment variables: "
                + ", ".join(missing)
                + ". Copy backend/.env.example to backend/.env and fill them in."
            )


config = Config()
