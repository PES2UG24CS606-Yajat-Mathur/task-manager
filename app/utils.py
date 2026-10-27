"""
Shared helpers: UTC time handling and consistent JSON responses.

Time convention used everywhere in the app
------------------------------------------
* Stored in the DB  : naive UTC text 'YYYY-MM-DDTHH:MM:SS'
* Sent to clients   : the same value with a trailing 'Z' (=> unambiguous UTC)
* Accepted from clients: any ISO-8601 string, with 'Z', with an offset
  (e.g. '2026-10-25T18:00:00+05:30') or a plain date ('2026-10-25' -> 23:59:59 that day).
"""

from datetime import datetime, timedelta, timezone

from flask import jsonify

DB_FORMAT = "%Y-%m-%dT%H:%M:%S"


def utcnow() -> datetime:
    """Current UTC time as a naive datetime, truncated to whole seconds."""
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def to_db(dt: datetime) -> str:
    """datetime -> DB text."""
    return dt.strftime(DB_FORMAT)


def now_db() -> str:
    """Shortcut: current UTC time as DB text."""
    return to_db(utcnow())


def from_db(value):
    """DB text -> datetime (or None)."""
    return datetime.strptime(value, DB_FORMAT) if value else None


def to_api(value):
    """DB text -> API text with 'Z' suffix (or None)."""
    return f"{value}Z" if value else None


def parse_client_datetime(value: str) -> datetime:
    """
    Parse a date/time sent by the client and normalise it to naive UTC.
    Raises ValueError for anything that is not ISO-8601.
    """
    text = value.strip()
    if len(text) == 10:                       # 'YYYY-MM-DD' -> end of that day (UTC)
        return datetime.strptime(text, "%Y-%m-%d") + timedelta(hours=23, minutes=59, seconds=59)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is not None:                 # convert offsets such as +05:30 to UTC
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.replace(microsecond=0)


def ok(payload=None, status_code: int = 200):
    """Uniform success envelope: {"status": "success", ...payload}."""
    body = {"status": "success"}
    body.update(payload or {})
    return jsonify(body), status_code
