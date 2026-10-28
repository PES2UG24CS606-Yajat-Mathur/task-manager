"""
Task Module (SAD 3.4) - create, view, edit, delete, complete/reopen + history.

Endpoints (SAD 4.3 API design)
------------------------------
GET    /api/tasks                 list my tasks (newest first)        TMA-F-010
POST   /api/tasks                 create a task                       TMA-F-010, TMA-F-020
GET    /api/tasks/<id>            one task                            TMA-F-014
PATCH  /api/tasks/<id>            edit title / description / priority TMA-F-011, TMA-F-020
DELETE /api/tasks/<id>            delete (UI confirms first)          TMA-F-012
POST   /api/tasks/<id>/complete   mark completed                      TMA-F-013
POST   /api/tasks/<id>/reopen     mark active again                   TMA-F-013
GET    /api/tasks/<id>/history    change log (TaskHistory)

Create-task flow follows SAD Figure 4:
  validateSession(token) -> createTask(details, userId) -> validateInput(details)
  -> [valid]   saveTask(task) -> 201 task created
  -> [invalid] 400 validation error with message
"""

import json

from flask import Blueprint, g

from .access import get_owned_task
from .db import query_all, query_one, transaction
from .errors import ValidationError
from .security import login_required
from .utils import now_db, ok, to_api
from .validators import clean_description, clean_priority, clean_title, get_json_body

bp = Blueprint("tasks", __name__, url_prefix="/api/tasks")

EDITABLE_FIELDS = {"title", "description", "priority"}


# ----------------------------------------------------------------- helpers
def task_to_dict(row) -> dict:
    """API representation of a task row."""
    return {
        "id": row["id"],
        "title": row["title"],
        "description": row["description"],
        "priority": row["priority"],          # LOW / MEDIUM / HIGH (TMA-F-020)
        "status": row["status"],
        "completedAt": to_api(row["completed_at"]),
        "createdAt": to_api(row["created_at"]),
        "updatedAt": to_api(row["updated_at"]),
    }


def load_task(task_id: int) -> dict:
    return task_to_dict(query_one("SELECT * FROM tasks WHERE id = ?", (task_id,)))


def add_history(db, task_id: int, change_type: str, details: dict):
    """TaskHistory row (UML: Task 1 -- 0..* TaskHistory 'logs')."""
    db.execute("INSERT INTO task_history (task_id, change_type, details, timestamp) "
               "VALUES (?,?,?,?)", (task_id, change_type, json.dumps(details), now_db()))


# ------------------------------------------------------------------ routes
@bp.get("")
@login_required
def list_tasks():
    # The WHERE user_id filter is what keeps other users' tasks out (TMA-F-014).
    rows = query_all("SELECT * FROM tasks WHERE user_id = ? ORDER BY created_at DESC, id DESC",
                     (g.user["id"],))
    return ok({"tasks": [task_to_dict(r) for r in rows], "count": len(rows)})


@bp.post("")
@login_required
def create_task():
    data = get_json_body()

    # 1) validateInput(details) - everything is checked before anything is written
    title = clean_title(data.get("title"))
    description = clean_description(data.get("description"))
    priority = clean_priority(data.get("priority") or "MEDIUM")    # default: MEDIUM

    # 2) saveTask(task) - task + its CREATED history entry in one transaction
    now = now_db()
    with transaction() as db:
        cur = db.execute(
            """INSERT INTO tasks (user_id, title, description, priority, created_at, updated_at)
               VALUES (?,?,?,?,?,?)""",
            (g.user["id"], title, description, priority, now, now),
        )
        task_id = cur.lastrowid
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

    # Keep only real changes so history stays meaningful.
    changes = {k: v for k, v in changes.items() if task[k] != v}
    if not changes:
        return ok({"task": load_task(task_id)})

    logged = dict(changes)
    changes["updated_at"] = now_db()
    with transaction() as db:
        # Column names come from our own whitelist above, never from user input.
        assignments = ", ".join(f"{col} = ?" for col in changes)
        db.execute(f"UPDATE tasks SET {assignments} WHERE id = ?",
                   (*changes.values(), task_id))
        add_history(db, task_id, "UPDATED", logged)

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
