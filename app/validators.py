"""
Input validation (SAD 4.4 "Validate required fields and return clear messages").

Design rule: validate EVERYTHING first, then write. Each function below either returns
cleaned values or raises a 400 ValidationError whose message tells the user exactly
what to fix. Because nothing is written until validation succeeds, a request with one
bad field can never leave a half-updated record behind (TMA-NF-004).

Feature PRs add the validators for their own fields to this file.
"""

import re

from flask import request

from .errors import ValidationError

PRIORITIES = ("LOW", "MEDIUM", "HIGH")          # <<enumeration>> Priority (SAD Figure 2)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
MAX_NAME = 100
MAX_TITLE, MAX_DESCRIPTION = 200, 2000


def get_json_body() -> dict:
    """Return the JSON object sent by the client, or raise 400."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")
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
