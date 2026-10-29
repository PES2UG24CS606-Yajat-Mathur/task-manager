"""
Access control for tasks (TMA-F-014, Test Plan TC-Sec-01).

Every task endpoint fetches the task through `get_owned_task()`. That single choke point
guarantees that ownership is checked on the SERVER for every task operation (view, edit,
and everything added later); hiding a button in the UI is never the only protection
(SAD 4.1).
"""

from flask import g, request

from .db import query_one
from .errors import Forbidden, NotFound
from .security import log_security_event


def get_owned_task(task_id: int):
    """Return the task row if it belongs to the logged-in user, else raise 404 / 403."""
    task = query_one("SELECT * FROM tasks WHERE id = ?", (task_id,))
    if task is None:
        raise NotFound("Task not found")
    if task["user_id"] != g.user["id"]:
        # Someone tried to touch another user's task: refuse, and record it (TMA-SR-005)
        log_security_event("ACCESS_DENIED", user_id=g.user["id"],
                           details={"path": request.path, "method": request.method,
                                    "task_id": task_id, "reason": "not task owner"})
        raise Forbidden("You do not have permission to access this task")
    return task
