"""
Task status rules (TMA-F-021) - how ACTIVE / COMPLETED / OVERDUE are decided.

The SAD class diagram has a Status enumeration with three values: ACTIVE, COMPLETED and
OVERDUE. Only the first two are STORED in tasks.status. OVERDUE is DERIVED every time a
task is read:

    stored status   due date                 status the user sees
    -------------   ----------------------   --------------------
    COMPLETED       anything                 COMPLETED
    ACTIVE          in the past              OVERDUE
    ACTIVE          in the future / none     ACTIVE

Why not store OVERDUE? A stored value would be wrong the moment a due date passes,
unless a background job kept rewriting rows. Deriving it in SQL means the task list, the
filters and the dashboard counts are always right (TMA-F-033). This is recorded as a
deviation from the SAD in docs/DEVIATIONS.md (D4).
"""

# Statuses a user may SET (PATCH {"status": ...}); OVERDUE is never accepted as input.
STORED_STATUSES = ("ACTIVE", "COMPLETED")
# Statuses a user may SEE (and filter on).
ALL_STATUSES = ("ACTIVE", "COMPLETED", "OVERDUE")


def effective_status_sql(alias: str = "t") -> str:
    """
    SQL expression that computes the status the user sees for table alias `alias`.
    The query must supply the current UTC time as the named parameter :now, e.g.

        SELECT t.*, {effective_status_sql('t')} AS effective_status
          FROM tasks t WHERE t.user_id = :user_id          -- params: {"now": now_db(), ...}

    Dates are stored as fixed-width ISO text, so `<` compares them chronologically.
    """
    return (f"CASE WHEN {alias}.status = 'COMPLETED' THEN 'COMPLETED' "
            f"WHEN {alias}.due_date IS NOT NULL AND {alias}.due_date < :now THEN 'OVERDUE' "
            f"ELSE 'ACTIVE' END")
