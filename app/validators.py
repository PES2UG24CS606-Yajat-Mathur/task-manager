"""
Input validation (SAD 4.4 "Validate required fields and return clear messages").

Design rule: validate EVERYTHING first, then write. Each function below either returns
cleaned values or raises a 400 ValidationError whose message tells the user exactly
what to fix. Because nothing is written until validation succeeds, a request with one
bad field can never leave a half-updated record behind (TMA-NF-004).

Feature PRs add the validators for their own fields to this file.
"""

import json
import re

from flask import request

from .errors import ValidationError
from .status import STORED_STATUSES
from .utils import parse_client_datetime, to_db

PRIORITIES = ("LOW", "MEDIUM", "HIGH")          # <<enumeration>> Priority (SAD Figure 2)
SORT_FIELDS = ("due_date", "priority", "status", "created_at", "title")   # TMA-F-032

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
MAX_NAME = 100
MAX_TITLE, MAX_DESCRIPTION = 200, 2000
MAX_CATEGORY = 50                               # longest category / tag name (TMA-F-022)
MIN_YEAR = 1900         # DEF-02: earlier years are not fixed-width in the DB text on every platform


def get_json_body() -> dict:
    """
    Return the JSON object sent by the client, or raise 400. Every route reads its body here,
    so these checks protect all of them:
      * DEF-05: JSON nested thousands of levels deep exhausts the parser (RecursionError).
      * DEF-04: "\\ud800" is valid JSON but decodes to text that cannot be encoded as UTF-8,
        so it would crash SQLite or the password hash later. Emoji arrive as a valid surrogate
        PAIR, which Python joins into one character, so real text is not affected.
    """
    try:
        data = request.get_json(silent=True)
    except RecursionError:
        raise ValidationError("Request body is nested too deeply") from None
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")
    try:
        json.dumps(data, ensure_ascii=False).encode("utf-8")
    except UnicodeEncodeError:
        raise ValidationError("Request contains text that is not valid Unicode") from None
    return data


# ------------------------------------------------------------------ users
def clean_name(value) -> str:
    name = (value or "").strip() if isinstance(value, str) else ""
    if not name:
        raise ValidationError("Name is required", {"field": "name"})
    if len(name) > MAX_NAME:
        raise ValidationError(f"Name must be at most {MAX_NAME} characters", {"field": "name"})
    return name


def clean_email(value) -> str:
    email = (value or "").strip().lower() if isinstance(value, str) else ""
    if not EMAIL_RE.match(email):
        raise ValidationError("Enter a valid email address", {"field": "email"})
    return email


def clean_password(value) -> str:
    """Password policy: 8-128 chars with at least one letter and one digit."""
    if not isinstance(value, str) or not (8 <= len(value) <= 128):
        raise ValidationError("Password must be 8 to 128 characters long", {"field": "password"})
    if not (re.search(r"[A-Za-z]", value) and re.search(r"\d", value)):
        raise ValidationError("Password must contain at least one letter and one number",
                              {"field": "password"})
    return value


# ------------------------------------------------------------------ tasks
def clean_title(value) -> str:
    title = value.strip() if isinstance(value, str) else ""
    if not title:
        raise ValidationError("Title is required", {"field": "title"})
    if len(title) > MAX_TITLE:
        raise ValidationError(f"Title must be at most {MAX_TITLE} characters", {"field": "title"})
    return title


def clean_description(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValidationError("Description must be text", {"field": "description"})
    if len(value) > MAX_DESCRIPTION:
        raise ValidationError(f"Description must be at most {MAX_DESCRIPTION} characters",
                              {"field": "description"})
    return value.strip()


def clean_priority(value) -> str:
    """'high' / 'HIGH' -> 'HIGH'; anything else -> 400 (TMA-F-020)."""
    priority = str(value or "").upper()
    if priority not in PRIORITIES:
        raise ValidationError("Priority must be one of LOW, MEDIUM, HIGH", {"field": "priority"})
    return priority


def clean_status(value) -> str:
    """
    TMA-F-021: a user may set ACTIVE or COMPLETED ('completed' is accepted too).
    OVERDUE is refused with its own message, because the app sets it automatically
    when the due date passes (see app/status.py).
    """
    status = str(value or "").upper()
    if status == "OVERDUE":
        raise ValidationError("OVERDUE is set automatically when the due date passes",
                              {"field": "status"})
    if status not in STORED_STATUSES:
        raise ValidationError("Status must be ACTIVE or COMPLETED", {"field": "status"})
    return status


# ------------------------------------------------------- due dates (TMA-F-023)
def clean_optional_datetime(value, field: str):
    """
    Validate an optional date/time sent by the client and return it as DB text (UTC).

        None or ""                      -> None   (no value / clear the existing value)
        "2026-10-30"                    -> "2026-10-30T23:59:59"   (end of that day, UTC)
        "2026-10-30T17:00:00Z"          -> "2026-10-30T17:00:00"
        "2026-10-30T17:00:00+05:30"     -> "2026-10-30T11:30:00"   (converted to UTC)
        "next friday", 42, ...          -> 400 ValidationError naming the field
        "0001-01-01T00:00:00+05:30"     -> 400 (DEF-02: UTC conversion would leave the calendar)
        "1899-12-31"                    -> 400 (DEF-02: before MIN_YEAR)

    `field` is the JSON key ("dueDate", later also "reminderTime"), so the error message
    tells the user exactly which input to fix.
    """
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be an ISO-8601 date string", {"field": field})
    try:
        parsed = parse_client_datetime(value)
        if parsed.year < MIN_YEAR:
            raise ValueError("year out of the supported range")
        return to_db(parsed)
    except (ValueError, OverflowError):
        raise ValidationError(f"{field} must be a valid date from {MIN_YEAR} onwards, e.g. 2026-10-30 "
                              f"or 2026-10-30T17:00:00Z", {"field": field}) from None


# ---------------------------------------------------- categories (TMA-F-022)
def clean_categories(value) -> list:
    """
    Validate a list of category names and return it cleaned:
      * surrounding spaces removed, empty names dropped
      * duplicates removed case-insensitively, first spelling kept, order kept
        (["College", "college", "SE"] -> ["College", "SE"])
    None means "no categories". Anything that is not a list of strings -> 400.
    """
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ValidationError("categories must be a list of names", {"field": "categories"})
    seen, result = set(), []
    for raw in value:
        name = raw.strip()
        if not name:
            continue
        if len(name) > MAX_CATEGORY:
            raise ValidationError(f"Category names must be at most {MAX_CATEGORY} characters",
                                  {"field": "categories"})
        if name.lower() not in seen:
            seen.add(name.lower())
            result.append(name)
    return result


# ------------------------------------------------------------ sorting (TMA-F-032)
def clean_sort(value) -> str:
    """One of SORT_FIELDS (default due_date), else 400."""
    sort = str(value or "due_date").lower()
    if sort not in SORT_FIELDS:
        raise ValidationError(f"sort must be one of {', '.join(SORT_FIELDS)}", {"field": "sort"})
    return sort
