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

from flask import Flask, request, send_from_directory
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
    _register_security_hooks(app)
    _register_core_routes(app)
    return app


def _register_modules(app: Flask):
    """Each SAD component is a Blueprint; every feature PR registers its own here."""
    from . import auth, dashboard, notifications, scheduling, tasks
    for module in (auth, tasks, scheduling, dashboard, notifications):
        app.register_blueprint(module.bp)
    app.cli.add_command(notifications.send_reminders_command)   # flask --app run send-reminders


def _register_security_hooks(app: Flask):
    @app.after_request
    def security_headers(response):
        """
        TMA-NF-003: defence-in-depth HTTP headers on every response.
          X-Content-Type-Options  browser must not guess file types (no "sniffing")
          X-Frame-Options         page cannot be shown inside another site's frame
          Referrer-Policy         task URLs are not leaked to other sites
          Content-Security-Policy only our own scripts and styles may run, so an
                                  injected <script> would be blocked (XSS)
          Cache-Control no-store  task data from /api/ is never cached on disk
        """
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "no-referrer")
        h.setdefault("Content-Security-Policy",
                     "default-src 'self'; img-src 'self' data:; style-src 'self'; "
                     "script-src 'self'; frame-ancestors 'none'; base-uri 'self'")
        if request.path.startswith("/api/"):
            h["Cache-Control"] = "no-store"
        return response


def _register_core_routes(app: Flask):
    @app.get("/")
    def index():
        """Serve the single-page UI."""
        return send_from_directory(app.static_folder, "index.html")
