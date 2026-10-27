"""
Authentication Module (SAD 3.4) - registration and login.

Endpoints
---------
POST  /api/auth/register   {name, email, password}  -> 201 {user}                     TMA-F-001
POST  /api/auth/login      {email, password}        -> 200 {userId, sessionToken, ...} TMA-F-002

Login follows SAD Figure 3: UI -> authenticate(email, password) -> getUserByEmail ->
on success return a session token (the browser sends it back as
"Authorization: Bearer <token>" on every later request).
"""

import sqlite3

from flask import Blueprint

from .db import query_one, transaction
from .errors import APIError, Conflict, ValidationError
from .security import create_session, hash_password, verify_password
from .utils import now_db, ok, to_api
from .validators import clean_email, clean_name, clean_password, get_json_body

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


def user_to_dict(row) -> dict:
    """Public representation of a user. Never includes the password hash."""
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "isActive": bool(row["is_active"]),
        "createdAt": to_api(row["created_at"]),
    }


def create_user(name: str, email: str, password: str, role: str = "user") -> int:
    """Insert a user and return the new id. Duplicate email -> 409 Conflict."""
    try:
        with transaction() as db:
            cur = db.execute(
                """INSERT INTO users (name, email, password_hash, role, created_at)
                   VALUES (?,?,?,?,?)""",
                (name, email, hash_password(password), role, now_db()),   # TMA-SR-002
            )
    except sqlite3.IntegrityError:
        # The UNIQUE constraint on users.email was violated -> account already exists
        raise Conflict("An account with this email already exists") from None
    return cur.lastrowid


# ------------------------------------------------------------------ routes
@bp.post("/register")
def register():
    data = get_json_body()
    # Validate every field first; nothing is written if any of them is invalid.
    name = clean_name(data.get("name"))
    email = clean_email(data.get("email"))
    password = clean_password(data.get("password"))

    user_id = create_user(name, email, password)
    user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    return ok({"user": user_to_dict(user)}, 201)


@bp.post("/login")
def login():
    data = get_json_body()
    email = str(data.get("email") or "").strip().lower()
    password = data.get("password")
    if not email or not isinstance(password, str) or not password:
        raise ValidationError("Email and password are required")

    user = query_one("SELECT * FROM users WHERE email = ?", (email,))
    if user is None or not verify_password(user["password_hash"], password):
        raise APIError(401, "INVALID_CREDENTIALS", "Invalid email or password")
    if not user["is_active"]:
        raise APIError(403, "ACCOUNT_DEACTIVATED", "This account has been deactivated")

    token, expires_at = create_session(user["id"])
    return ok({
        "userId": user["id"],
        "sessionToken": token,          # shown to the client once; DB keeps only its hash
        "expiresAt": to_api(expires_at),
        "user": user_to_dict(user),
    })
