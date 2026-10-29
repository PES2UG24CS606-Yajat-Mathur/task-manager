"""
Administration Module (SAD 3.4) - user / account management for administrators.

Every endpoint needs the 'admin' role (@admin_required: 401 if not logged in, 403 if not
an admin), and every administrative action is written to the security log (TMA-SR-005).

GET    /api/admin/users                         list users with their task counts   TMA-F-042
PATCH  /api/admin/users/<id>  {role?, isActive?} promote / demote, (de)activate
DELETE /api/admin/users/<id>                    delete an account and all its data
GET    /api/admin/security-events?type=&limit=  review recent activity
                                                (Administrator.reviewActivity in the UML)

Safety rules
* An admin cannot deactivate, demote or delete their OWN account (no lock-out).
* Deactivating a user logs them out everywhere at once (all their sessions are revoked).

The first administrator is created from the command line, never through the web:
    flask --app run create-admin          (asks for name, email and password)
"""

import json

import click
from flask import Blueprint, g, request
from flask.cli import with_appcontext

from .auth import create_user, user_to_dict
from .db import query_all, query_one, transaction
from .errors import NotFound, ValidationError
from .security import admin_required, log_security_event, revoke_all_sessions
from .utils import ok, to_api
from .validators import clean_email, clean_name, clean_password, get_json_body

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


def _get_user_or_404(user_id: int):
    user = query_one("SELECT * FROM users WHERE id = ?", (user_id,))
    if user is None:
        raise NotFound("User not found")
    return user


@bp.get("/users")
@admin_required
def list_users():
    # LEFT JOIN keeps users who have no tasks (their count is 0)
    rows = query_all("""SELECT u.*, COUNT(t.id) AS task_count
                          FROM users u LEFT JOIN tasks t ON t.user_id = u.id
                         GROUP BY u.id ORDER BY u.id""")
    return ok({"users": [{**user_to_dict(r), "taskCount": r["task_count"]} for r in rows]})


@bp.patch("/users/<int:user_id>")
@admin_required
def update_user(user_id: int):
    target = _get_user_or_404(user_id)
    data = get_json_body()
    changes = {}
    if "role" in data:
        if data["role"] not in ("user", "admin"):
            raise ValidationError("role must be 'user' or 'admin'", {"field": "role"})
        changes["role"] = data["role"]
    if "isActive" in data:
        if not isinstance(data["isActive"], bool):
            raise ValidationError("isActive must be true or false", {"field": "isActive"})
        changes["is_active"] = int(data["isActive"])
    if not changes:
        raise ValidationError("Nothing to update: send role and/or isActive")

    # Safety rule: an admin cannot lock themselves out.
    if user_id == g.user["id"] and (changes.get("is_active") == 0 or changes.get("role") == "user"):
        raise ValidationError("You cannot deactivate or demote your own account")

    with transaction() as db:
        assignments = ", ".join(f"{col} = ?" for col in changes)   # whitelisted columns only
        db.execute(f"UPDATE users SET {assignments} WHERE id = ?", (*changes.values(), user_id))
        if changes.get("is_active") == 0:
            revoke_all_sessions(user_id, db)       # deactivated users are logged out at once

    log_security_event("ADMIN_UPDATE_USER", user_id=g.user["id"],
                       details={"target_user_id": user_id, "target_email": target["email"],
                                "changes": dict(changes)})
    return ok({"user": user_to_dict(_get_user_or_404(user_id))})


@bp.delete("/users/<int:user_id>")
@admin_required
def delete_user(user_id: int):
    target = _get_user_or_404(user_id)
    if user_id == g.user["id"]:
        raise ValidationError("You cannot delete your own account")
    with transaction() as db:          # cascades to sessions, tasks, categories, reminders...
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    log_security_event("ADMIN_DELETE_USER", user_id=g.user["id"],
                       details={"target_user_id": user_id, "target_email": target["email"]})
    return ok({"message": "User deleted"})


@bp.get("/security-events")
@admin_required
def security_events():
    try:
        limit = min(max(int(request.args.get("limit", 100)), 1), 500)
    except ValueError:
        raise ValidationError("limit must be an integer") from None
    sql, params = "SELECT * FROM security_events", []
    if request.args.get("type"):
        sql += " WHERE event_type = ?"
        params.append(request.args["type"].upper())
    rows = query_all(sql + " ORDER BY id DESC LIMIT ?", (*params, limit))
    return ok({"events": [{"id": r["id"], "type": r["event_type"], "userId": r["user_id"],
                           "email": r["email"], "ip": r["ip_address"],
                           "details": json.loads(r["details"]),
                           "createdAt": to_api(r["created_at"])} for r in rows]})


# ------------------------------------------------------------------ CLI
@click.command("create-admin")
@click.option("--name", prompt=True)
@click.option("--email", prompt=True)
@click.password_option("--password")   # asked twice and hidden; never typed on the command line
@with_appcontext
def create_admin_command(name, email, password):
    """CLI:  flask --app run create-admin"""
    try:
        user_id = create_user(clean_name(name), clean_email(email), clean_password(password),
                              role="admin")
    except Exception as err:              # show validation / duplicate-email messages nicely
        raise click.ClickException(getattr(err, "message", str(err)))
    click.echo(f"Administrator created with id {user_id}")
