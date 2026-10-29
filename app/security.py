"""
Security building blocks shared by every module (SAD 3.9 "Security Architecture").

| Requirement | How it is implemented here                                              |
|-------------|-------------------------------------------------------------------------|
| TMA-SR-002  | hash_password / verify_password -> werkzeug scrypt (salted, slow hash)  |
| TMA-SR-003  | @login_required on every protected route, @admin_required for admin-only|
|             | routes, ownership checks in access.py; all enforced on the server       |
| TMA-SR-004  | random 256-bit session tokens; the database keeps only SHA-256(token);  |
|             | expiry and logout (revocation) are checked on every request             |
| TMA-SR-005  | log_security_event() -> security_events table + application log, after |
|             | a filter that removes anything that looks like a password or a token    |
"""

import hashlib
import json
import secrets
from datetime import timedelta
from functools import wraps

from flask import current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db, query_one, transaction
from .errors import Forbidden, Unauthorized
from .utils import now_db, to_db, utcnow

# Keys that must never be written to a log, whatever a caller passes in (TMA-SR-005).
_SENSITIVE_KEYS = {"password", "new_password", "token", "sessiontoken", "authorization",
                   "password_hash", "secret"}


# ------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    """
    Return a salted, deliberately slow hash, e.g. 'scrypt:32768:8:1$<salt>$<hash>'.
    The random salt means two users with the same password get different hashes,
    and the slowness makes guessing passwords from a stolen database impractical.
    """
    return generate_password_hash(password, method=current_app.config["PASSWORD_HASH_METHOD"])


def verify_password(password_hash: str, password: str) -> bool:
    """Re-hash the attempt with the stored salt and compare in constant time."""
    return check_password_hash(password_hash, password)


# ---------------------------------------------------------------- tokens
def hash_token(token: str) -> str:
    """SHA-256 is enough here: tokens are random 256-bit values, not guessable passwords."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id: int):
    """
    Create a login session and return (raw_token, expires_at).
    The raw token goes to the browser ONCE; the database keeps only its hash,
    so a leaked database cannot be used to log in as anyone.
    """
    token = secrets.token_urlsafe(32)                   # 32 bytes = 256 bits of randomness
    now = utcnow()
    expires = now + timedelta(hours=current_app.config["SESSION_LIFETIME_HOURS"])
    with transaction() as db:
        db.execute(
            "INSERT INTO sessions (user_id, token_hash, created_at, expires_at) VALUES (?,?,?,?)",
            (user_id, hash_token(token), to_db(now), to_db(expires)),
        )
    return token, to_db(expires)


def revoke_session(session_id: int):
    """Logout: mark the session as revoked so its token can never be used again."""
    with transaction() as db:
        db.execute("UPDATE sessions SET revoked_at = ? WHERE id = ? AND revoked_at IS NULL",
                   (now_db(), session_id))


def _bearer_token():
    """Extract the token from the header 'Authorization: Bearer <token>'."""
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def _load_current_user():
    """Validate the bearer token and return the user row (+ session info), or raise 401."""
    token = _bearer_token()
    if not token:
        raise Unauthorized("Authentication required")
    row = query_one(
        """SELECT s.id AS session_id, s.expires_at, s.revoked_at, u.*
             FROM sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ?""",
        (hash_token(token),),                 # we look the token up by its hash
    )
    if row is None:
        raise Unauthorized("Invalid session token")
    if row["revoked_at"] is not None:
        raise Unauthorized("Session has been logged out")
    if row["expires_at"] <= now_db():
        raise Unauthorized("Session has expired, please log in again")
    if not row["is_active"]:
        raise Unauthorized("Account is deactivated")
    return row


# ------------------------------------------------------------ decorators
def login_required(view):
    """
    Put @login_required under a route to reject the request with 401 unless it carries a
    valid, unexpired, not-logged-out token. The route can then use g.user.
    """
    @wraps(view)
    def wrapper(*args, **kwargs):
        row = _load_current_user()
        g.user = row                       # the authenticated user, for the route to use
        g.session_id = row["session_id"]
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    """
    TMA-SR-003: like @login_required, plus the user must have the 'admin' role, else 403.
    Used by the administration endpoints (TMA-F-042).
    """
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if g.user["role"] != "admin":
            # TMA-SR-005: a non-admin trying an admin page is worth recording
            log_security_event("ACCESS_DENIED", user_id=g.user["id"],
                               details={"path": request.path, "reason": "admin role required"})
            raise Forbidden("Administrator access required")
        return view(*args, **kwargs)
    return wrapper


# ------------------------------------------------- security event log (TMA-SR-005)
def _is_sensitive(key: str) -> bool:
    """'Password', 'new_password', 'X-Auth-Token', 'sessionToken' ... -> True."""
    norm = key.lower().replace("-", "").replace("_", "")
    return (norm in {k.replace("_", "") for k in _SENSITIVE_KEYS}
            or "password" in norm or "token" in norm)


def _scrub(details: dict) -> dict:
    """Return a copy of `details` with every sensitive key removed, at any depth."""
    clean = {}
    for key, value in (details or {}).items():
        if _is_sensitive(str(key)):
            continue
        clean[key] = _scrub(value) if isinstance(value, dict) else value
    return clean


def log_security_event(event_type: str, user_id=None, email=None, details=None):
    """
    Record a security-relevant event (failed login, logout, access denied, admin action...)
    in the security_events table AND in the application log. Never records passwords or
    tokens: `details` goes through _scrub() first.
    """
    safe = _scrub(details)
    ip = request.remote_addr if request else None
    # Callers log AFTER their own transaction has finished, so this insert (autocommit)
    # stands on its own: the audit record is kept even when the operation itself failed.
    get_db().execute(
        """INSERT INTO security_events (event_type, user_id, email, ip_address, details,
                                        created_at) VALUES (?,?,?,?,?,?)""",
        (event_type, user_id, email, ip, json.dumps(safe), now_db()),
    )
    current_app.logger.info("security_event=%s user_id=%s email=%s ip=%s details=%s",
                            event_type, user_id, email, ip, safe)


def recent_failed_logins(email: str, minutes: int) -> int:
    """How many LOGIN_FAILED events this email had in the last `minutes` minutes."""
    since = to_db(utcnow() - timedelta(minutes=minutes))
    row = query_one("""SELECT COUNT(*) AS n FROM security_events
                        WHERE event_type = 'LOGIN_FAILED' AND email = ? AND created_at >= ?""",
                    (email, since))
    return row["n"]
