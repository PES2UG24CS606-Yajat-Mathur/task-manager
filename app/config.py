"""
Configuration classes. Pick one with the APP_ENV environment variable:
    APP_ENV=development (default) | production | testing

Every value can also be overridden with an environment variable of the same name,
so nothing secret has to be committed to the repository.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool) -> bool:
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes", "on")


class Config:
    # Used by Flask for signing; generate one with: python -c "import secrets;print(secrets.token_hex())"
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    DATABASE = os.environ.get("DATABASE", str(BASE_DIR / "instance" / "taskmanager.sqlite3"))
    MAX_CONTENT_LENGTH = 64 * 1024   # reject request bodies larger than 64 KB

    # --- security -------------------------------------------------------------
    SESSION_LIFETIME_HOURS = int(os.environ.get("SESSION_LIFETIME_HOURS", 8))   # TMA-SR-004
    PASSWORD_HASH_METHOD = os.environ.get("PASSWORD_HASH_METHOD", "scrypt")      # TMA-SR-002
    MAX_FAILED_LOGINS = int(os.environ.get("MAX_FAILED_LOGINS", 5))       # per email ...
    FAILED_LOGIN_WINDOW_MIN = int(os.environ.get("FAILED_LOGIN_WINDOW_MIN", 15))  # ... per window
    # TMA-SR-001: redirect http:// to https:// and send HSTS
    FORCE_HTTPS = _env_bool("FORCE_HTTPS", False)
    # Behind a reverse proxy (nginx, Render, ...) that ends TLS and sets X-Forwarded-Proto
    TRUST_PROXY = _env_bool("TRUST_PROXY", False)

    # --- notifications (TMA-F-024, TMA-F-040) ------------------------------------
    REMINDER_POLL_SECONDS = int(os.environ.get("REMINDER_POLL_SECONDS", 30))  # scheduler interval
    EMAIL_NOTIFICATIONS_ENABLED = _env_bool("EMAIL_NOTIFICATIONS_ENABLED", False)

    TESTING = False
    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    FORCE_HTTPS = _env_bool("FORCE_HTTPS", True)   # HTTPS is on by default in production


class TestingConfig(Config):
    TESTING = True
    # Fast hash so the test-suite runs in seconds; production keeps scrypt.
    PASSWORD_HASH_METHOD = "pbkdf2:sha256:1000"
    FORCE_HTTPS = False


CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
