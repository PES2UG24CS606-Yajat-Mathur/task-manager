"""
Authentication Module (SAD 3.4) - registration, login, logout and profile.

Endpoints
---------
POST  /api/auth/register   {name, email, password}  -> 201 {user}                     TMA-F-001
POST  /api/auth/login      {email, password}        -> 200 {userId, sessionToken, ...} TMA-F-002
                                                     -> 401 "Invalid email or password"  TMA-F-003
POST  /api/auth/logout     (Bearer token)           -> 200                              TMA-F-004
GET   /api/auth/me         (Bearer token)           -> 200 {user}
PATCH /api/auth/me         {name?, email?}          -> 200 {user}   (User.updateProfile)

Login follows SAD Figure 3: UI -> authenticate(email, password) -> getUserByEmail ->
on success return a session token (the browser sends it back as
"Authorization: Bearer <token>" on every later request).

Security logging (TMA-SR-005): REGISTER, LOGIN_SUCCESS, LOGIN_FAILED, LOGIN_BLOCKED and
LOGOUT events are recorded in security_events, never with the password.
Brute-force protection: after MAX_FAILED_LOGINS (5) failures for one email within
FAILED_LOGIN_WINDOW_MIN (15) minutes, logins for that email get 429 until the window passes.
"""

import sqlite3

from flask import Blueprint, current_app, g

from .db import query_one, transaction
from .errors import APIError, Conflict, TooManyRequests, ValidationError
from .security import (create_session, hash_password, log_security_event, login_required,
                       recent_failed_logins, revoke_session, verify_password)
from .utils import now_db, ok, to_api
from .validators import clean_email, clean_name, clean_password, get_json_body

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

# A real-looking hash used when the email does not exist, so a failed login takes the
# same time whether or not the account exists (an attacker cannot use response time
# to find out which emails are registered).
_DUMMY_HASH = None


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
    log_security_event("REGISTER", user_id=user_id, email=email)
    return ok({"user": user_to_dict(user)}, 201)


@bp.post("/login")
def login():
    global _DUMMY_HASH
    data = get_json_body()
    email = str(data.get("email") or "").strip().lower()
    password = data.get("password")
    if not email or not isinstance(password, str) or not password:
        raise ValidationError("Email and password are required")

    # Brute-force protection (SAD 3.9 STRIDE: spoofing / denial of service).
    # Checked BEFORE the password, so even the right password waits out the lockout.
    cfg = current_app.config
    if recent_failed_logins(email, cfg["FAILED_LOGIN_WINDOW_MIN"]) >= cfg["MAX_FAILED_LOGINS"]:
        log_security_event("LOGIN_BLOCKED", email=email)
        raise TooManyRequests(f"Too many failed attempts. Try again in "
                              f"{cfg['FAILED_LOGIN_WINDOW_MIN']} minutes.")

    user = query_one("SELECT * FROM users WHERE email = ?", (email,))
    if user is None:
        if _DUMMY_HASH is None:
            _DUMMY_HASH = hash_password("dummy-password-1")
        verify_password(_DUMMY_HASH, password)      # equalise timing, result ignored
        valid = False
    else:
        valid = verify_password(user["password_hash"], password)

    if not valid:
        # TMA-F-003: reject, create NO session, and use the same message for
        # "no such account" and "wrong password" so emails cannot be enumerated.
        # TMA-SR-005: record the failure (the attempted password is never logged).
        log_security_event("LOGIN_FAILED", user_id=user["id"] if user else None, email=email,
                           details={"reason": "invalid credentials"})
        raise APIError(401, "INVALID_CREDENTIALS", "Invalid email or password")
    if not user["is_active"]:
        log_security_event("LOGIN_FAILED", user_id=user["id"], email=email,
                           details={"reason": "account deactivated"})
        raise APIError(403, "ACCOUNT_DEACTIVATED", "This account has been deactivated")

    token, expires_at = create_session(user["id"])
    log_security_event("LOGIN_SUCCESS", user_id=user["id"], email=email)
    return ok({
        "userId": user["id"],
        "sessionToken": token,          # shown to the client once; DB keeps only its hash
        "expiresAt": to_api(expires_at),
        "user": user_to_dict(user),
    })


@bp.post("/logout")
@login_required
def logout():
    revoke_session(g.session_id)        # TMA-F-004 / TMA-SR-004: token is dead from now on
    log_security_event("LOGOUT", user_id=g.user["id"], email=g.user["email"])
    return ok({"message": "Logged out"})


@bp.get("/me")
@login_required
def me():
    return ok({"user": user_to_dict(g.user)})


@bp.patch("/me")
@login_required
def update_profile():
    data = get_json_body()
    name = clean_name(data["name"]) if "name" in data else g.user["name"]
    email = clean_email(data["email"]) if "email" in data else g.user["email"]
    try:
        with transaction() as db:
            db.execute("UPDATE users SET name = ?, email = ? WHERE id = ?",
                       (name, email, g.user["id"]))
    except sqlite3.IntegrityError:
        raise Conflict("An account with this email already exists") from None
    user = query_one("SELECT * FROM users WHERE id = ?", (g.user["id"],))
    return ok({"user": user_to_dict(user)})
