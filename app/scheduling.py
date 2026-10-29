"""
Scheduling Module (SAD 3.4) - categories / tags and due dates.

Endpoints
---------
GET    /api/categories                 list my categories, with how many tasks use each   TMA-F-022
POST   /api/categories   {name}        create a category on its own                       TMA-F-022
DELETE /api/categories/<id>            delete a category (its tasks are kept, just untagged)

Categories are also "created or selected" straight from the task form: a task is saved
with a list of names, e.g. {"title": ..., "categories": ["College", "SE"]}. Names that
already exist are reused, new names are created (ensure_categories below).

Due dates are a plain task field (POST / PATCH /api/tasks with "dueDate"), validated by
validators.clean_optional_datetime (TMA-F-023).

Data model (SAD Figure 2): Task 0..* <-> 0..* Category, stored in the link table
task_categories. Categories belong to ONE user: every query below filters on user_id,
so nobody can see or delete another person's categories.
"""

from flask import Blueprint, g

from .db import query_all, query_one, transaction
from .errors import Conflict, NotFound, ValidationError
from .security import login_required
from .utils import ok
from .validators import MAX_CATEGORY, get_json_body

bp = Blueprint("scheduling", __name__, url_prefix="/api")


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
