"""
Input validation (SAD 4.4 "Validate required fields and return clear messages").

Design rule: validate EVERYTHING first, then write. Each function below either returns
cleaned values or raises a 400 ValidationError whose message tells the user exactly
what to fix. Because nothing is written until validation succeeds, a request with one
bad field can never leave a half-updated record behind (TMA-NF-004).

Feature PRs add the validators for their own fields to this file.
"""

from flask import request

from .errors import ValidationError


def get_json_body() -> dict:
    """Return the JSON object sent by the client, or raise 400."""
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a JSON object")
    return data
