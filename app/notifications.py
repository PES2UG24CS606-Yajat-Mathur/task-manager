"""
Notification Module (SAD 3.4) - reminders become notifications; user preferences.

Endpoints
---------
GET   /api/notifications?unread=true        my in-app notifications (newest first)   TMA-F-040
POST  /api/notifications/<id>/read          mark one as read
POST  /api/notifications/read-all           mark all as read
GET   /api/preferences                      my notification + task preferences       TMA-F-041
PUT   /api/preferences                      change them                               TMA-F-041

How a reminder fires (Reminder.trigger() in the UML)
----------------------------------------------------
`process_due_reminders()` finds reminders whose time has come and that were not sent
yet, and creates one notification on every channel the user has switched on. It is
called from three places, so reminders work however the app is run:
  1. a background thread started by run.py, every REMINDER_POLL_SECONDS (30 s by default)
  2. the command line:  flask --app run send-reminders   (for cron / Task Scheduler)
  3. lazily, whenever the user opens GET /api/notifications
Each reminder is "claimed" with UPDATE ... WHERE delivered = 0, so even if two of these
run at the same moment, a reminder is delivered exactly once.

Channels
--------
* in_app : saved in the notifications table and shown behind the Notifications button.
* email  : `EmailNotifier` is an interface-level stub. The Test Plan (section 4) tests
           third-party notification services only at the interface, and the SAD (4.6)
           leaves the choice of provider open. A real SMTP / provider call goes in send().
"""

import threading
import time

import click
from flask import Blueprint, current_app, g, request
from flask.cli import with_appcontext

from .db import get_db, query_all, query_one, transaction
from .errors import NotFound, ValidationError
from .security import login_required
from .utils import now_db, ok, to_api
from .validators import clean_priority, clean_sort, get_json_body

bp = Blueprint("notifications", __name__, url_prefix="/api")

CHANNELS = ("in_app", "email")
# What a user gets before they ever save preferences (no notification_preferences rows).
DEFAULT_CHANNELS = {"in_app": True, "email": False}


# ======================================================================= service
class EmailNotifier:
    """Notification Service interface (SAD Figure 1, 'where enabled')."""

    def send(self, to_address: str, subject: str, body: str) -> bool:
        """Return True if the e-mail was handed to the provider."""
        if not current_app.config["EMAIL_NOTIFICATIONS_ENABLED"]:
            return False
        # Stub: a real integration (SMTP, SendGrid, ...) goes here.
        current_app.logger.info("EMAIL to=%s subject=%s", to_address, subject)
        return True


email_notifier = EmailNotifier()


def _channel_settings(db, user_id: int) -> dict:
    """{channel: enabled}: the defaults, overridden by whatever the user has saved."""
    settings = dict(DEFAULT_CHANNELS)
    rows = db.execute("SELECT channel, enabled FROM notification_preferences WHERE user_id = ?",
                      (user_id,)).fetchall()
    settings.update({r["channel"]: bool(r["enabled"]) for r in rows})
    return settings


def process_due_reminders(user_id=None, now=None) -> int:
    """
    Deliver every reminder that is due and return how many notifications were created.
    `user_id` limits it to one user (the lazy trigger); `now` lets tests move the clock.
    """
    now = now or now_db()
    sql = """SELECT r.id AS reminder_id, r.task_id, t.title, t.status, t.user_id, u.email
               FROM reminders r
               JOIN tasks t ON t.id = r.task_id
               JOIN users u ON u.id = t.user_id
              WHERE r.delivered = 0 AND r.reminder_time <= ? AND u.is_active = 1"""
    params = [now]
    if user_id is not None:
        sql += " AND t.user_id = ?"
        params.append(user_id)

    created = 0
    for rem in query_all(sql, params):
        with transaction() as db:
            # Claim the reminder. If another worker got there first, rowcount is 0: skip it.
            claimed = db.execute("UPDATE reminders SET delivered = 1, delivered_at = ? "
                                 "WHERE id = ? AND delivered = 0",
                                 (now, rem["reminder_id"])).rowcount
            if not claimed or rem["status"] == "COMPLETED":
                continue                    # no point reminding about finished work
            message = f"Reminder: '{rem['title']}'"
            enabled = [c for c, on in _channel_settings(db, rem["user_id"]).items() if on]
            for channel in enabled:
                if channel == "email" and not email_notifier.send(
                        rem["email"], "Task reminder", message):
                    continue
                db.execute("""INSERT INTO notifications (user_id, task_id, reminder_id, channel,
                                                          message, created_at)
                              VALUES (?,?,?,?,?,?)""",
                           (rem["user_id"], rem["task_id"], rem["reminder_id"], channel,
                            message, now))
                created += 1
    return created


def start_reminder_scheduler(app):
    """Start a background thread that delivers due reminders every REMINDER_POLL_SECONDS."""
    interval = app.config["REMINDER_POLL_SECONDS"]

    def loop():
        while True:
            try:
                with app.app_context():
                    count = process_due_reminders()
                    if count:
                        app.logger.info("Delivered %d reminder notification(s)", count)
            except Exception:                      # never let one bad run stop the thread
                app.logger.exception("Reminder scheduler iteration failed")
            time.sleep(interval)

    thread = threading.Thread(target=loop, name="reminder-scheduler", daemon=True)
    thread.start()
    return thread


@click.command("send-reminders")
@with_appcontext
def send_reminders_command():
    """CLI:  flask --app run send-reminders"""
    click.echo(f"Created {process_due_reminders()} notification(s)")


# ======================================================================== routes
def notification_to_dict(row) -> dict:
    return {"id": row["id"], "taskId": row["task_id"], "channel": row["channel"],
            "message": row["message"], "taskDueDate": to_api(row["due_date"]),
            "createdAt": to_api(row["created_at"]), "read": row["read_at"] is not None}


@bp.get("/notifications")
@login_required
def list_notifications():
    process_due_reminders(user_id=g.user["id"])          # lazy trigger (see module doc)
    sql = """SELECT n.*, t.due_date FROM notifications n
               LEFT JOIN tasks t ON t.id = n.task_id
              WHERE n.user_id = ? AND n.channel = 'in_app'"""
    if request.args.get("unread") in ("1", "true", "yes"):
        sql += " AND n.read_at IS NULL"
    rows = query_all(sql + " ORDER BY n.id DESC LIMIT 50", (g.user["id"],))
    unread = query_one("SELECT COUNT(*) AS n FROM notifications WHERE user_id = ? "
                       "AND channel = 'in_app' AND read_at IS NULL", (g.user["id"],))["n"]
    return ok({"notifications": [notification_to_dict(r) for r in rows], "unread": unread})


@bp.post("/notifications/<int:notification_id>/read")
@login_required
def mark_read(notification_id: int):
    with transaction() as db:
        # "AND user_id = ?" -> someone else's notification looks like a missing one (404)
        changed = db.execute("UPDATE notifications SET read_at = COALESCE(read_at, ?) "
                             "WHERE id = ? AND user_id = ?",
                             (now_db(), notification_id, g.user["id"])).rowcount
    if not changed:
        raise NotFound("Notification not found")
    return ok({"message": "Marked as read"})


@bp.post("/notifications/read-all")
@login_required
def mark_all_read():
    with transaction() as db:
        db.execute("UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL",
                   (now_db(), g.user["id"]))
    return ok({"message": "All notifications marked as read"})


def _preferences(user_id: int) -> dict:
    user = query_one("SELECT default_priority, default_sort FROM users WHERE id = ?",
                     (user_id,))
    return {"notifications": _channel_settings(get_db(), user_id),
            "defaultPriority": user["default_priority"], "defaultSort": user["default_sort"]}


@bp.get("/preferences")
@login_required
def get_preferences():
    return ok({"preferences": _preferences(g.user["id"])})


@bp.put("/preferences")
@login_required
def update_preferences():
    """
    Body (every key optional):
      {"notifications": {"in_app": true, "email": false},
       "defaultPriority": "HIGH", "defaultSort": "priority"}
    Everything is validated first, then saved in one transaction (TMA-NF-004).
    """
    data = get_json_body()
    channels = data.get("notifications", {})
    if not isinstance(channels, dict) or any(c not in CHANNELS for c in channels):
        raise ValidationError(f"notifications must map {', '.join(CHANNELS)} to true/false")
    if any(not isinstance(v, bool) for v in channels.values()):
        raise ValidationError("Notification settings must be true or false")
    priority = clean_priority(data["defaultPriority"]) if "defaultPriority" in data else None
    sort = clean_sort(data["defaultSort"]) if "defaultSort" in data else None

    with transaction() as db:
        for channel, enabled in channels.items():   # NotificationPreference.update()
            # "upsert": insert the row, or update it if this user already has one
            db.execute("""INSERT INTO notification_preferences (user_id, channel, enabled)
                          VALUES (?,?,?)
                          ON CONFLICT(user_id, channel) DO UPDATE SET enabled = excluded.enabled""",
                       (g.user["id"], channel, int(enabled)))
        if priority:
            db.execute("UPDATE users SET default_priority = ? WHERE id = ?",
                       (priority, g.user["id"]))
        if sort:
            db.execute("UPDATE users SET default_sort = ? WHERE id = ?", (sort, g.user["id"]))
    return ok({"preferences": _preferences(g.user["id"])})
