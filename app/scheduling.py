"""
Scheduling Module (SAD 3.4) - categories / tags, due dates and reminders.

Endpoints
---------
GET    /api/categories                 list my categories, with how many tasks use each   TMA-F-022
POST   /api/categories   {name}        create a category on its own                       TMA-F-022
DELETE /api/categories/<id>            delete a category (its tasks are kept, just untagged)
GET    /api/tasks/<id>/reminders       list a task's reminders                            TMA-F-024
POST   /api/tasks/<id>/reminders       {reminderTime} or {minutesBefore}                  TMA-F-024
DELETE /api/reminders/<id>             remove a reminder

Categories are also "created or selected" straight from the task form: a task is saved
with a list of names, e.g. {"title": ..., "categories": ["College", "SE"]}. Names that
already exist are reused, new names are created (ensure_categories below).

Due dates are a plain task field (POST / PATCH /api/tasks with "dueDate"), validated by
validators.clean_optional_datetime (TMA-F-023).

Reminders (TMA-F-024) are stored here; the Notification Module (notifications.py) turns
the ones that are due into notifications (TMA-F-040).

Data model (SAD Figure 2): Task 0..* <-> 0..* Category, stored in the link table
task_categories. Categories belong to ONE user: every query below filters on user_id,
so nobody can see or delete another person's categories.
"""

from datetime import timedelta

from flask import Blueprint, g

from .access import get_owned_task
from .db import query_all, query_one, transaction
from .errors import Conflict, NotFound, ValidationError
from .security import login_required
from .utils import from_db, now_db, ok, to_api, to_db
from .validators import MAX_CATEGORY, clean_optional_datetime, get_json_body

bp = Blueprint("scheduling", __name__, url_prefix="/api")

MAX_MINUTES_BEFORE = 7 * 24 * 60   # a reminder can be at most one week before the due date


# ============================================================== category helpers
# These run INSIDE the caller's transaction (`db`), so a task and its category links are
# saved together or not at all (TMA-NF-004).

def ensure_categories(db, user_id: int, names: list) -> list:
    """
    "Create or select" categories by name and return their ids, in the same order.
    INSERT OR IGNORE skips names the user already has (UNIQUE(user_id, name) with
    COLLATE NOCASE, so "college" reuses an existing "College").
    """
    ids = []
    for name in names:
        db.execute("INSERT OR IGNORE INTO categories (user_id, name) VALUES (?, ?)",
                   (user_id, name))
        row = db.execute("SELECT id FROM categories WHERE user_id = ? AND name = ?",
                         (user_id, name)).fetchone()
        ids.append(row["id"])
    return ids


def set_task_categories(db, task_id: int, category_ids: list):
    """Replace a task's categories with exactly `category_ids`."""
    db.execute("DELETE FROM task_categories WHERE task_id = ?", (task_id,))
    db.executemany("INSERT INTO task_categories (task_id, category_id) VALUES (?, ?)",
                   [(task_id, cid) for cid in category_ids])


def categories_for_tasks(task_ids: list) -> dict:
    """
    {task_id: ["College", "SE"], ...} for MANY tasks with ONE query.
    (Asking once per task would be the "N+1 queries" problem and would slow the task
    list down as it grows, which matters for TMA-NF-001.)
    """
    if not task_ids:
        return {}
    marks = ",".join("?" * len(task_ids))          # "?,?,?" - one placeholder per id
    rows = query_all(f"""SELECT tc.task_id, c.name FROM task_categories tc
                           JOIN categories c ON c.id = tc.category_id
                          WHERE tc.task_id IN ({marks})
                          ORDER BY c.name COLLATE NOCASE""", task_ids)
    result = {tid: [] for tid in task_ids}
    for row in rows:
        result[row["task_id"]].append(row["name"])
    return result


# ============================================================== category routes
@bp.get("/categories")
@login_required
def list_categories():
    rows = query_all("""SELECT c.id, c.name, COUNT(tc.task_id) AS task_count
                          FROM categories c
                          LEFT JOIN task_categories tc ON tc.category_id = c.id
                         WHERE c.user_id = ?
                         GROUP BY c.id ORDER BY c.name COLLATE NOCASE""", (g.user["id"],))
    return ok({"categories": [{"id": r["id"], "name": r["name"], "taskCount": r["task_count"]}
                              for r in rows]})


@bp.post("/categories")
@login_required
def create_category():
    name = get_json_body().get("name")
    name = name.strip() if isinstance(name, str) else ""
    if not name or len(name) > MAX_CATEGORY:
        raise ValidationError(f"Category name is required (max {MAX_CATEGORY} characters)",
                              {"field": "name"})
    if query_one("SELECT 1 FROM categories WHERE user_id = ? AND name = ?",
                 (g.user["id"], name)):
        raise Conflict("You already have a category with this name")
    with transaction() as db:
        cur = db.execute("INSERT INTO categories (user_id, name) VALUES (?, ?)",
                         (g.user["id"], name))
    return ok({"category": {"id": cur.lastrowid, "name": name, "taskCount": 0}}, 201)


@bp.delete("/categories/<int:category_id>")
@login_required
def delete_category(category_id: int):
    # Filtering on user_id means "someone else's category" looks exactly like
    # "no such category" (404), so ids of other users' categories are not revealed.
    row = query_one("SELECT * FROM categories WHERE id = ? AND user_id = ?",
                    (category_id, g.user["id"]))
    if row is None:
        raise NotFound("Category not found")
    with transaction() as db:            # ON DELETE CASCADE removes the task_categories links
        db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    return ok({"message": "Category deleted"})


# ============================================================== reminder helpers
def reminder_to_dict(row) -> dict:
    return {"id": row["id"], "taskId": row["task_id"],
            "reminderTime": to_api(row["reminder_time"]),
            "delivered": bool(row["delivered"]), "deliveredAt": to_api(row["delivered_at"])}


def resolve_reminder_time(data: dict, due_date_db):
    """
    Work out WHEN a reminder should fire (Reminder.configure in the UML). Two ways:
      {"reminderTime": "2026-10-28T09:00:00Z"}  -> exactly that time
      {"minutesBefore": 30}                     -> 30 minutes before the task's due date
    Returns DB text, or None if the request asks for no reminder. Raises 400 when the
    input is invalid or the time has already passed.
    """
    if data.get("reminderTime") not in (None, ""):
        when = clean_optional_datetime(data["reminderTime"], "reminderTime")
    elif data.get("minutesBefore") not in (None, ""):
        if not due_date_db:
            raise ValidationError("Set a due date before using minutesBefore",
                                  {"field": "minutesBefore"})
        try:
            minutes = int(data["minutesBefore"])
        except (TypeError, ValueError):
            raise ValidationError("minutesBefore must be a whole number",
                                  {"field": "minutesBefore"}) from None
        if not 0 <= minutes <= MAX_MINUTES_BEFORE:
            raise ValidationError(f"minutesBefore must be between 0 and {MAX_MINUTES_BEFORE}",
                                  {"field": "minutesBefore"})
        when = to_db(from_db(due_date_db) - timedelta(minutes=minutes))
    else:
        return None
    if when <= now_db():
        raise ValidationError("Reminder time must be in the future", {"field": "reminderTime"})
    return when


def next_reminders_for_tasks(task_ids: list) -> dict:
    """{task_id: earliest reminder that has not fired yet (DB text) or None}, in ONE query."""
    if not task_ids:
        return {}
    marks = ",".join("?" * len(task_ids))
    rows = query_all(f"""SELECT task_id, MIN(reminder_time) AS next_time FROM reminders
                          WHERE delivered = 0 AND task_id IN ({marks})
                          GROUP BY task_id""", task_ids)
    result = {tid: None for tid in task_ids}
    result.update({r["task_id"]: r["next_time"] for r in rows})
    return result


# ============================================================== reminder routes
@bp.get("/tasks/<int:task_id>/reminders")
@login_required
def list_reminders(task_id: int):
    get_owned_task(task_id)              # 404 / 403 unless it is my task
    rows = query_all("SELECT * FROM reminders WHERE task_id = ? ORDER BY reminder_time",
                     (task_id,))
    return ok({"reminders": [reminder_to_dict(r) for r in rows]})


@bp.post("/tasks/<int:task_id>/reminders")
@login_required
def add_reminder(task_id: int):
    task = get_owned_task(task_id)
    when = resolve_reminder_time(get_json_body(), task["due_date"])
    if when is None:
        raise ValidationError("Provide reminderTime or minutesBefore")
    with transaction() as db:
        cur = db.execute("INSERT INTO reminders (task_id, reminder_time) VALUES (?, ?)",
                         (task_id, when))
    row = query_one("SELECT * FROM reminders WHERE id = ?", (cur.lastrowid,))
    return ok({"reminder": reminder_to_dict(row)}, 201)


@bp.delete("/reminders/<int:reminder_id>")
@login_required
def delete_reminder(reminder_id: int):
    row = query_one("SELECT * FROM reminders WHERE id = ?", (reminder_id,))
    if row is None:
        raise NotFound("Reminder not found")
    get_owned_task(row["task_id"])       # ownership is checked through the parent task
    with transaction() as db:
        db.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))
    return ok({"message": "Reminder deleted"})
