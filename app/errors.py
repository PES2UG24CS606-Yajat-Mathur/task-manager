"""
Consistent API error structure (SAD 4.4 "Use consistent API error structures").

Every error the API returns looks like:
    {
      "status": "error",
      "error": {"code": "VALIDATION_ERROR", "message": "Title is required", "details": {...}}
    }

Route code simply raises `APIError(...)` (or one of the shortcuts below) and the
handlers registered here turn it into that JSON shape with the right HTTP status.
"""

from flask import jsonify, request
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    """An error that should be shown to the API client."""

    def __init__(self, status_code: int, code: str, message: str, details=None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


# Shortcuts so route code reads naturally:  raise NotFound("Task not found")
def ValidationError(message, details=None):      # noqa: N802 (factory named like a class)
    return APIError(400, "VALIDATION_ERROR", message, details)


def Unauthorized(message="Authentication required"):   # noqa: N802
    return APIError(401, "UNAUTHORIZED", message)


def Forbidden(message="You do not have permission to access this resource"):  # noqa: N802
    return APIError(403, "FORBIDDEN", message)


def NotFound(message="Resource not found"):       # noqa: N802
    return APIError(404, "NOT_FOUND", message)


def Conflict(message):                            # noqa: N802
    return APIError(409, "CONFLICT", message)


def TooManyRequests(message):                     # noqa: N802
    return APIError(429, "TOO_MANY_REQUESTS", message)


def _error_body(status_code, code, message, details=None):
    body = {"status": "error", "error": {"code": code, "message": message}}
    if details:
        body["error"]["details"] = details
    return jsonify(body), status_code


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(err: APIError):
        return _error_body(err.status_code, err.code, err.message, err.details)

    @app.errorhandler(HTTPException)
    def handle_http_error(err: HTTPException):
        # Only JSON-ify API routes; static pages keep Flask's normal behaviour.
        if request.path.startswith("/api/"):
            code = (err.name or "HTTP_ERROR").upper().replace(" ", "_")
            return _error_body(err.code, code, err.description or err.name)
        return err

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        # Log the full traceback server-side, but never leak internals to the client.
        app.logger.exception("Unhandled error on %s %s", request.method, request.path)
        return _error_body(500, "INTERNAL_ERROR", "An unexpected error occurred")
