"""
Application Database layer (SAD component "Application Database").

Uses Python's built-in sqlite3 module, so the project needs nothing but Flask.

Key ideas
---------
* One connection per request, stored on `flask.g`, closed automatically at teardown.
* Rows come back as `sqlite3.Row`, which behaves like a dict (row["title"]).
* `transaction()` wraps a block in BEGIN ... COMMIT, and ROLLS BACK on any exception.
  Every write in the app goes through it, which is how TMA-NF-004 (data consistency)
  is guaranteed: a task update either fully happens or does not happen at all.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

import click
from flask import current_app, g
from flask.cli import with_appcontext

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


def _connect(path: str) -> sqlite3.Connection:
    """Open a connection configured the way the whole app expects."""
    conn = sqlite3.connect(
        path,
        isolation_level=None,          # autocommit mode; we issue BEGIN/COMMIT ourselves
        check_same_thread=False,       # the reminder scheduler thread opens its own connection
        timeout=10,                    # wait up to 10 s if another writer holds the lock
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")   # SQLite needs this per connection
    conn.execute("PRAGMA journal_mode = WAL")  # readers never block the writer
    return conn


def get_db() -> sqlite3.Connection:
    """Return this request's connection, opening it on first use."""
    if "db" not in g:
        g.db = _connect(current_app.config["DATABASE"])
    return g.db


def close_db(_exc=None):
    """Teardown hook: close the request's connection if one was opened."""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@contextmanager
def transaction():
    """
    Usage:
        with transaction() as db:
            db.execute("INSERT ...")
            db.execute("UPDATE ...")
    Both statements commit together, or neither does.
    """
    db = get_db()
    db.execute("BEGIN IMMEDIATE")     # take the write lock up front -> no lost updates
    try:
        yield db
    except Exception:
        db.execute("ROLLBACK")
        raise
    else:
        db.execute("COMMIT")


# ---------------------------------------------------------------- helpers
def query_one(sql: str, params=()):
    """Run a SELECT and return the first row (or None)."""
    return get_db().execute(sql, params).fetchone()


def query_all(sql: str, params=()):
    """Run a SELECT and return all rows as a list."""
    return get_db().execute(sql, params).fetchall()


def init_db():
    """Create every table/index defined in schema.sql (safe to run repeatedly)."""
    Path(current_app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    get_db().executescript(SCHEMA_FILE.read_text(encoding="utf-8"))


@click.command("init-db")
@with_appcontext
def init_db_command():
    """CLI:  flask --app run init-db"""
    init_db()
    click.echo(f"Initialised database at {current_app.config['DATABASE']}")


def register_db(app):
    """Wire the database into the Flask app (teardown + CLI command)."""
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
