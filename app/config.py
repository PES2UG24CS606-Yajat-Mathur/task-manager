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

    TESTING = False
    DEBUG = False


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    pass


class TestingConfig(Config):
    TESTING = True


CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
