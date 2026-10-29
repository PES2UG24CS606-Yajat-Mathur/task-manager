"""
Task Manager Application - Flask application factory.

Architecture (SAD 3.5): a layered monolith with modular components.

    Presentation      app/static/ (HTML/CSS/JS single-page UI)           User / Admin UI
    API / modules     one Flask Blueprint per SAD component              (added PR by PR)
    Cross-cutting     security.py, validators.py, errors.py, utils.py
    Persistence       db.py + schema.sql (SQLite)                        Application Database

`create_app()` builds a fully configured app; tests call it with a temporary database.
"""

import logging
import os

from flask import Flask, send_from_directory
from flask.logging import default_handler

from .config import CONFIGS
from .db import init_db, register_db
from .errors import register_error_handlers


def create_app(config_name=None, overrides=None) -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")

    # ---------------------------------------------------------------- config
    config_name = config_name or os.environ.get("APP_ENV", "development")
    app.config.from_object(CONFIGS[config_name])
    app.config.update(overrides or {})
    app.logger.setLevel(logging.WARNING if app.testing else logging.INFO)
    app.logger.removeHandler(default_handler)   # log once, via the root handler below

    logging.basicConfig(level=logging.WARNING if app.testing else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    # --------------------------------------------------- database + errors
    register_db(app)
    register_error_handlers(app)
    with app.app_context():
        init_db()          # CREATE TABLE IF NOT EXISTS ... -> safe on every start

    _register_modules(app)
    _register_core_routes(app)
    return app


def _register_modules(app: Flask):
    """Each SAD component is a Blueprint; every feature PR registers its own here."""
    from . import auth, scheduling, tasks
    for module in (auth, tasks, scheduling):
        app.register_blueprint(module.bp)


def _register_core_routes(app: Flask):
    @app.get("/")
    def index():
        """Serve the single-page UI."""
        return send_from_directory(app.static_folder, "index.html")
