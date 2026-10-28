"""
Security building blocks shared by every module (SAD 3.9 "Security Architecture").

| Requirement | How it is implemented here                                              |
|-------------|-------------------------------------------------------------------------|
| TMA-SR-002  | hash_password / verify_password -> werkzeug scrypt (salted, slow hash)  |
| TMA-SR-004  | random 256-bit session tokens; the database keeps only SHA-256(token);  |
|             | expiry and logout (revocation) are checked on every request             |
"""

import hashlib
import secrets
from datetime import timedelta
from functools import wraps

from flask import current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from .db import query_one, transaction
from .errors import Unauthorized
from .utils import now_db, to_db, utcnow


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
