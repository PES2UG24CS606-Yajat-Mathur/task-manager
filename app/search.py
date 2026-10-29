"""
Search Module (SAD 3.4) - search, filter and sort a user's tasks.

This module only BUILDS the SQL; the Task Module's GET /api/tasks runs it. Keeping the
query-building separate makes it easy to test and to reason about.

Query-string parameters for GET /api/tasks (all optional, all combinable)
-------------------------------------------------------------------------
q          keyword, matched case-insensitively in the title OR the description  TMA-F-030
status     ACTIVE | COMPLETED | OVERDUE   (comma separated for several)         TMA-F-031
priority   LOW | MEDIUM | HIGH            (comma separated for several)         TMA-F-031
category   one category name (case-insensitive)                                TMA-F-031
sort       due_date | priority | status | created_at | title                    TMA-F-032
order      asc (default) | desc
limit, offset  paging: at most 500 tasks per request

Examples
    /api/tasks?q=report&status=ACTIVE,OVERDUE&sort=priority
    /api/tasks?category=College&sort=due_date&order=desc

Security: user input never becomes part of the SQL text. Every value is passed as a
named parameter (:kw, :st0, ...), and the ORDER BY clause is picked from a fixed table
of our own strings, so SQL injection is not possible (TMA-NF-003).
"""

from .errors import ValidationError
from .status import ALL_STATUSES, effective_status_sql
from .validators import PRIORITIES, clean_sort

# Rank expressions so that ascending order means "most important first".
_PRIORITY_RANK = "CASE t.priority WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END"
_STATUS_RANK = ("CASE effective_status WHEN 'OVERDUE' THEN 1 WHEN 'ACTIVE' THEN 2 "
                "ELSE 3 END")
MAX_LIMIT = 500


def _csv_values(raw, allowed, field):
    """'high, low' -> ['HIGH', 'LOW'], after checking every value is allowed (else 400)."""
    values = [v.strip().upper() for v in raw.split(",") if v.strip()]
    bad = [v for v in values if v not in allowed]
    if bad:
        raise ValidationError(f"Invalid {field}: {', '.join(bad)}. "
                              f"Allowed: {', '.join(allowed)}", {"field": field})
    return values


def _in_clause(prefix: str, values: list, params: dict) -> str:
    """['HIGH', 'LOW'] -> ':pr0, :pr1' and adds {'pr0': 'HIGH', 'pr1': 'LOW'} to params."""
    keys = [f"{prefix}{i}" for i in range(len(values))]
    params.update(zip(keys, values))
    return ", ".join(":" + k for k in keys)


def _like_escape(text: str) -> str:
    """
    In SQL LIKE, '%' and '_' are wildcards. Escape them so a search for "50%" matches
    the literal text "50%" instead of "50 anything".
    """
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def build_task_query(user_id: int, args, now: str, default_sort: str = "due_date"):
    """
    Return (sql, params) selecting the user's tasks with the filters and sorting applied.
    `args` is request.args (or any dict-like object). Raises 400 for invalid values.
    """
    params = {"user_id": user_id, "now": now}
    where = ["t.user_id = :user_id"]           # the ownership filter is ALWAYS applied

    # ---- TMA-F-030: keyword search in title or description
    keyword = (args.get("q") or "").strip()
    if keyword:
        params["kw"] = f"%{_like_escape(keyword)}%"
        # LIKE is case-insensitive for ASCII letters in SQLite
        where.append("(t.title LIKE :kw ESCAPE '\\' OR t.description LIKE :kw ESCAPE '\\')")

    # ---- TMA-F-031: filters
    if args.get("status"):
        statuses = _csv_values(args["status"], ALL_STATUSES, "status")
        where.append(f"effective_status IN ({_in_clause('st', statuses, params)})")
    if args.get("priority"):
        priorities = _csv_values(args["priority"], PRIORITIES, "priority")
        where.append(f"t.priority IN ({_in_clause('pr', priorities, params)})")
    category = (args.get("category") or "").strip()
    if category:
        params["category"] = category
        # categories.name is COLLATE NOCASE, so "college" finds "College"
        where.append("""EXISTS (SELECT 1 FROM task_categories tc
                                  JOIN categories c ON c.id = tc.category_id
                                 WHERE tc.task_id = t.id AND c.name = :category)""")

    # ---- TMA-F-032: sorting
    sort = clean_sort(args.get("sort") or default_sort)
    order = (args.get("order") or "asc").lower()
    if order not in ("asc", "desc"):
        raise ValidationError("order must be asc or desc", {"field": "order"})
    direction = order.upper()
    order_by = {
        # Tasks without a due date always go last, whichever direction is chosen.
        "due_date": f"t.due_date IS NULL, t.due_date {direction}",
        # Ties are broken by the due date, soonest first.
        "priority": f"{_PRIORITY_RANK} {direction}, t.due_date IS NULL, t.due_date ASC",
        "status": f"{_STATUS_RANK} {direction}, t.due_date IS NULL, t.due_date ASC",
        "created_at": f"t.created_at {direction}",
        "title": f"t.title COLLATE NOCASE {direction}",
    }[sort]

    # ---- paging
    try:
        limit = min(max(int(args.get("limit", 100)), 1), MAX_LIMIT)
        offset = max(int(args.get("offset", 0)), 0)
    except (TypeError, ValueError):
        raise ValidationError("limit and offset must be integers") from None
    params.update(limit=limit, offset=offset)

    # The inner SELECT works out effective_status once, so WHERE and ORDER BY can use it.
    sql = f"""
        SELECT * FROM (
            SELECT t.*, {effective_status_sql('t')} AS effective_status
              FROM tasks t
             WHERE t.user_id = :user_id
        ) AS t
        WHERE {' AND '.join(where)}
        ORDER BY {order_by}, t.id ASC
        LIMIT :limit OFFSET :offset
    """
    return sql, params
