"""
Task Module (SAD 3.4) - create, view, edit, delete, complete/reopen + history.

Endpoints (SAD 4.3 API design)
------------------------------
GET    /api/tasks                 list / search / filter / sort       TMA-F-010, F-030..032
POST   /api/tasks                 create a task                       TMA-F-010, F-020..023
GET    /api/tasks/<id>            one task                            TMA-F-014
PATCH  /api/tasks/<id>            edit fields                         TMA-F-011, F-020..023
DELETE /api/tasks/<id>            delete (UI confirms first)          TMA-F-012
POST   /api/tasks/<id>/complete   mark completed                      TMA-F-013
POST   /api/tasks/<id>/reopen     mark active again                   TMA-F-013
GET    /api/tasks/<id>/history    change log (TaskHistory)

Task fields in the JSON API
---------------------------
title, description, priority (LOW/MEDIUM/HIGH), status, isOverdue, dueDate (ISO-8601,
UTC with 'Z'), categories (list of names), nextReminder, completedAt, createdAt, updatedAt.

POST /api/tasks may also carry "reminderTime" or "minutesBefore" to set a first reminder
in the same step (TMA-F-024). New tasks get the user's default priority, and the list
uses the user's default sort, unless the request says otherwise (TMA-F-041).

`status` is what the user SEES: ACTIVE, COMPLETED or OVERDUE. Only ACTIVE / COMPLETED are
stored; OVERDUE is worked out from the due date on every read (app/status.py, TMA-F-021).

Create-task flow follows SAD Figure 4:
  validateSession(token) -> createTask(details, userId) -> validateInput(details)
  -> [valid]   saveTask(task) -> 201 task created
  -> [invalid] 400 validation error with message
"""

import json

from flask import Blueprint, g, request

from .access import get_owned_task
from .db import query_all, query_one, transaction
from .errors import ValidationError
from .scheduling import (categories_for_tasks, ensure_categories, next_reminders_for_tasks,
                         resolve_reminder_time, set_task_categories)
from .search import build_task_query
from .security import login_required
from .status import effective_status_sql
from .utils import now_db, ok, to_api
from .validators import (clean_categories, clean_description, clean_optional_datetime,
                         clean_priority, clean_status, clean_title, get_json_body)

bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")

# JSON keys a PATCH may contain. Anything else (e.g. "user_id") is rejected with 400.
EDITABLE_FIELDS = {"title", "description", "priority", "status", "dueDate", "categories"}

# Every task read goes through this SELECT, so OVERDUE is computed the same way everywhere.
# Queries using it must pass the current time as the named parameter :now.
TASK_SELECT = f"SELECT t.*, {effective_status_sql('t')} AS effective_status FROM tasks t"


# ----------------------------------------------------------------- helpers
def task_to_dict(row, categories=None, next_reminder=None) -> dict:
    """API representation of one task row (+ its category names and next reminder)."""
    # Rows from TASK_SELECT carry the derived status; a plain row falls back to the stored one.
    status = row["effective_status"] if "effective_status" in row.keys() else row["status"]
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "priority": row["priority"],          # LOW / MEDIUM / HIGH (TMA-F-020)
        "status": status,                     # ACTIVE / COMPLETED / OVERDUE (TMA-F-021)
        "isOverdue": status == "OVERDUE",
        "dueDate": to_api(row["due_date"]),   # TMA-F-023, None when not set
        "categories": categories or [],       # TMA-F-022
        "nextReminder": to_api(next_reminder),  # TMA-F-024, earliest reminder not yet sent
        "completedAt": to_api(row["completed_at"]),
        "createdAt": to_api(row["created_at"]),
        "updatedAt": to_api(row["updated_at"]),
    }


def serialize_tasks(rows) -> list:
    """Turn many task rows into API dicts: one query for categories, one for reminders."""
    ids = [r["id"] for r in rows]
    cats, reminders = categories_for_tasks(ids), next_reminders_for_tasks(ids)
    return [task_to_dict(r, cats[r["id"]], reminders[r["id"]]) for r in rows]


def load_task(task_id: int) -> dict:
    row = query_one(f"{TASK_SELECT} WHERE t.id = :id", {"id": task_id, "now": now_db()})
    return serialize_tasks([row])[0]


def add_history(db, task_id: int, change_type: str, details: dict):
    """TaskHistory row (UML: Task 1 -- 0..* TaskHistory 'logs')."""
    db.execute("INSERT INTO task_history (task_id, change_type, details, timestamp) "
               "VALUES (?,?,?,?)", (task_id, change_type, json.dumps(details), now_db()))


# ------------------------------------------------------------------ routes
@bp.get("")
@login_required
def list_tasks():
    # The Search Module builds the query from ?q=&status=&priority=&category=&sort=&order=
    # and ALWAYS filters on user_id, which keeps other users' tasks out (TMA-F-014).
    sql, params = build_task_query(g.user["id"], request.args, now_db(),
                                   default_sort=g.user["default_sort"])     # TMA-F-041
    rows = query_all(sql, params)
    return ok({"tasks": serialize_tasks(rows), "count": len(rows)})


@bp.post("")
@login_required
def create_task():
    data = get_json_body()

    # 1) validateInput(details) - everything is checked before anything is written
    title = clean_title(data.get("title"))
    description = clean_description(data.get("description"))
    # No priority given -> the user's default from Preferences (TMA-F-041), MEDIUM at first
    priority = clean_priority(data.get("priority") or g.user["default_priority"])
    status = clean_status(data.get("status") or "ACTIVE")           # TMA-F-021
    due_date = clean_optional_datetime(data.get("dueDate"), "dueDate")      # TMA-F-023
    categories = clean_categories(data.get("categories"))                   # TMA-F-022
    reminder_time = resolve_reminder_time(data, due_date)   # TMA-F-024, None = no reminder

    # 2) saveTask(task) - task + categories + reminder + history in ONE transaction
    now = now_db()
    with transaction() as db:
        cur = db.execute(
            """INSERT INTO tasks (user_id, title, description, priority, status, due_date,
                                  completed_at, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (g.user["id"], title, description, priority, status, due_date,
             now if status == "COMPLETED" else None, now, now),
        )
        task_id = cur.lastrowid
        set_task_categories(db, task_id, ensure_categories(db, g.user["id"], categories))
        if reminder_time:
            db.execute("INSERT INTO reminders (task_id, reminder_time) VALUES (?, ?)",
                       (task_id, reminder_time))
        add_history(db, task_id, "CREATED", {"title": title, "priority": priority})

    return ok({"taskId": task_id, "task": load_task(task_id)}, 201)


@bp.get("/<int:task_id>")
@login_required
def get_task(task_id: int):
    get_owned_task(task_id)
    return ok({"task": load_task(task_id)})


@bp.patch("/<int:task_id>")
@login_required
def update_task(task_id: int):
    task = get_owned_task(task_id)
    data = get_json_body()

    unknown = set(data) - EDITABLE_FIELDS
    if unknown:
        raise ValidationError(f"Unknown field(s): {', '.join(sorted(unknown))}")

    # Validate every supplied field first; build the column -> value changes.
    changes = {}
    if "title" in data:
        changes["title"] = clean_title(data["title"])
    if "description" in data:
        changes["description"] = clean_description(data["description"])
    if "priority" in data:
        changes["priority"] = clean_priority(data["priority"])
    if "status" in data:                        # TMA-F-021: ACTIVE <-> COMPLETED
        changes["status"] = clean_status(data["status"])
    if "dueDate" in data:                       # null / "" clears the due date
        changes["due_date"] = clean_optional_datetime(data["dueDate"], "dueDate")
    # Categories live in another table, so they are handled separately from `changes`.
    new_categories = clean_categories(data["categories"]) if "categories" in data else None

    # Keep only real changes so history stays meaningful.
    changes = {k: v for k, v in changes.items() if task[k] != v}
    if not changes and new_categories is None:
        return ok({"task": load_task(task_id)})

    logged = dict(changes)
    if new_categories is not None:
        logged["categories"] = new_categories
    now = now_db()
    if "status" in changes:                     # keep completed_at consistent with status
        changes["completed_at"] = now if changes["status"] == "COMPLETED" else None
    changes["updated_at"] = now
    with transaction() as db:
        # Column names come from our own whitelist above, never from user input.
        assignments = ", ".join(f"{col} = ?" for col in changes)
        db.execute(f"UPDATE tasks SET {assignments} WHERE id = ?",
                   (*changes.values(), task_id))
        if new_categories is not None:
            set_task_categories(db, task_id,
                                ensure_categories(db, g.user["id"], new_categories))
        # A status change is logged like the Complete / Reopen buttons log it.
        change_type = {"COMPLETED": "COMPLETED", "ACTIVE": "REOPENED"}.get(
            changes.get("status"), "UPDATED")
        add_history(db, task_id, change_type, logged)

    return ok({"task": load_task(task_id)})


@bp.delete("/<int:task_id>")
@login_required
def delete_task(task_id: int):
    get_owned_task(task_id)
    with transaction() as db:
        # ON DELETE CASCADE also removes reminders, category links and history
        # (UML composition: Reminder and TaskHistory cannot exist without their Task).
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    return ok({"message": "Task deleted"})


def _set_status(task_id: int, status: str):
    task = get_owned_task(task_id)
    if task["status"] != status:
        now = now_db()
        with transaction() as db:
            db.execute("UPDATE tasks SET status = ?, completed_at = ?, updated_at = ? "
                       "WHERE id = ?",
                       (status, now if status == "COMPLETED" else None, now, task_id))
            add_history(db, task_id, "COMPLETED" if status == "COMPLETED" else "REOPENED",
                        {"status": status})
    return ok({"task": load_task(task_id)})


@bp.post("/<int:task_id>/complete")
@login_required
def complete_task(task_id: int):          # Task.markComplete()
    return _set_status(task_id, "COMPLETED")


@bp.post("/<int:task_id>/reopen")
@login_required
def reopen_task(task_id: int):            # Task.reopen()
    return _set_status(task_id, "ACTIVE")


@bp.get("/<int:task_id>/history")
@login_required
def task_history(task_id: int):
    get_owned_task(task_id)
    rows = query_all("SELECT * FROM task_history WHERE task_id = ? ORDER BY id", (task_id,))
    return ok({"history": [{"id": r["id"], "changeType": r["change_type"],
                            "details": json.loads(r["details"]),
                            "timestamp": to_api(r["timestamp"])} for r in rows]})
