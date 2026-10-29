"""Progress summary - TC-Progress-01 (TMA-F-033)."""

from datetime import timedelta

from app.utils import to_db, utcnow
from tests.helpers import APITestCase


def iso_in(**delta) -> str:
    """UTC ISO string `delta` from now, e.g. iso_in(days=2)."""
    return to_db(utcnow() + timedelta(**delta)) + "Z"


class TestDashboard(APITestCase):
    def summary(self, headers):
        return self.client.get("/api/dashboard/summary", headers=headers).get_json()

    def test_TC_Progress_01_counts_match_task_data(self):
        h = self.new_user()
        for i in range(3):
            self.create_task(h, title=f"active {i}", priority="HIGH" if i == 0 else "LOW")
        self.create_task(h, title="late", dueDate="2020-01-01T00:00:00Z")
        for i in range(2):
            t = self.create_task(h, title=f"done {i}")
            self.client.post(f"/api/tasks/{t['id']}/complete", headers=h)

        summary = self.summary(h)["summary"]
        self.assertEqual((summary["active"], summary["overdue"], summary["completed"]), (3, 1, 2))
        self.assertEqual(summary["total"], 6)
        self.assertEqual(summary["active"] + summary["overdue"] + summary["completed"],
                         summary["total"])
        self.assertEqual(summary["completionRate"], round(100 * 2 / 6, 1))
        self.assertEqual(summary["byPriority"], {"HIGH": 1, "MEDIUM": 1, "LOW": 2})

        # Cross-check against the task list itself: same rule, same numbers
        tasks = self.list_tasks(h)
        for status in ("ACTIVE", "OVERDUE", "COMPLETED"):
            self.assertEqual(summary[status.lower()],
                             sum(1 for t in tasks if t["status"] == status))

    def test_due_soon_lists_open_tasks_due_this_week(self):
        h = self.new_user()
        self.create_task(h, title="tomorrow", dueDate=iso_in(days=1))
        self.create_task(h, title="in 3 days", dueDate=iso_in(days=3))
        self.create_task(h, title="next month", dueDate=iso_in(days=30))     # too far
        self.create_task(h, title="already late", dueDate=iso_in(days=-1))   # overdue, not "soon"
        done = self.create_task(h, title="done", dueDate=iso_in(days=2))
        self.client.post(f"/api/tasks/{done['id']}/complete", headers=h)    # finished
        titles = [t["title"] for t in self.summary(h)["dueSoon"]]
        self.assertEqual(titles, ["tomorrow", "in 3 days"])                  # soonest first

    def test_empty_dashboard(self):
        summary = self.summary(self.new_user())["summary"]
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["completionRate"], 0.0)

    def test_other_users_tasks_not_counted(self):
        a, b = self.new_user("a@example.com"), self.new_user("b@example.com")
        self.create_task(a)
        self.assertEqual(self.summary(b)["summary"]["total"], 0)
        self.assertEqual(self.client.get("/api/dashboard/summary").status_code, 401)
