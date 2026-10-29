"""
Dashboard Module (SAD 3.4) - progress summary of active, completed and overdue tasks.

GET /api/dashboard/summary  ->
{
  "summary": {"total": 12, "active": 6, "completed": 4, "overdue": 2,
              "completionRate": 33.3,
              "byPriority": {"HIGH": 3, "MEDIUM": 5, "LOW": 4}},   # open tasks only
  "dueSoon": [ ...up to 5 open tasks due in the next 7 days, soonest first... ]
}

TMA-F-033 acceptance: "Dashboard counts match the underlying task data".
* The counts use the SAME status rule as the task list (status.effective_status_sql),
  so a task shown as Overdue in the list is counted as overdue here.
* The three buckets never overlap, so active + completed + overdue == total.
* Everything is counted by the database in one query (no Python loops over tasks),
  which keeps the dashboard fast as the task list grows (TMA-NF-001).
"""

from datetime import timedelta

from flask import Blueprint, g

from .db import query_all, query_one
from .security import login_required
from .status import effective_status_sql
from .tasks import TASK_SELECT, serialize_tasks
from .utils import now_db, ok, to_db, utcnow

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


@bp.get("/summary")
@login_required
def summary():
    params = {"user_id": g.user["id"], "now": now_db()}
    status = effective_status_sql("t")

    # One pass over the user's tasks: COUNT(*) for the total, and SUM(CASE ... THEN 1)
    # to count only the rows matching each condition. COALESCE turns "no rows" into 0.
    counts = query_one(f"""
        SELECT COUNT(*)                                                        AS total,
               COALESCE(SUM(CASE WHEN {status} = 'ACTIVE'    THEN 1 END), 0)   AS active,
               COALESCE(SUM(CASE WHEN {status} = 'COMPLETED' THEN 1 END), 0)   AS completed,
               COALESCE(SUM(CASE WHEN {status} = 'OVERDUE'   THEN 1 END), 0)   AS overdue,
               COALESCE(SUM(CASE WHEN t.status = 'ACTIVE' AND t.priority = 'HIGH'
                                 THEN 1 END), 0)                               AS open_high,
               COALESCE(SUM(CASE WHEN t.status = 'ACTIVE' AND t.priority = 'MEDIUM'
                                 THEN 1 END), 0)                               AS open_medium,
               COALESCE(SUM(CASE WHEN t.status = 'ACTIVE' AND t.priority = 'LOW'
                                 THEN 1 END), 0)                               AS open_low
          FROM tasks t WHERE t.user_id = :user_id""", params)

    # "Due in the next 7 days": open tasks whose due date is between now and now + 7 days.
    params["soon"] = to_db(utcnow() + timedelta(days=7))
    due_soon = query_all(f"""
        {TASK_SELECT}
         WHERE t.user_id = :user_id AND t.status = 'ACTIVE'
           AND t.due_date IS NOT NULL AND t.due_date >= :now AND t.due_date <= :soon
         ORDER BY t.due_date LIMIT 5""", params)

    total = counts["total"]
    return ok({
        "summary": {
            "total": total,
            "active": counts["active"],
            "completed": counts["completed"],
            "overdue": counts["overdue"],
            # Percentage with one decimal; 0.0 (not a division by zero) when there are no tasks
            "completionRate": round(100 * counts["completed"] / total, 1) if total else 0.0,
            "byPriority": {"HIGH": counts["open_high"], "MEDIUM": counts["open_medium"],
                           "LOW": counts["open_low"]},
        },
        "dueSoon": serialize_tasks(due_soon),
    })
