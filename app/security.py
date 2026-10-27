"""
Security building blocks shared by every module (SAD 3.9 "Security Architecture").

| Requirement | How it is implemented here                                              |
|-------------|-------------------------------------------------------------------------|
| TMA-SR-002  | hash_password / verify_password -> werkzeug scrypt (salted, slow hash)  |
| TMA-SR-004  | random 256-bit session tokens; the database keeps only SHA-256(token)   |
"""

import hashlib
import secrets
from datetime import timedelta

from flask import current_app
from werkzeug.security import check_password_hash, generate_password_hash

from .db import transaction
from .utils import to_db, utcnow


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
