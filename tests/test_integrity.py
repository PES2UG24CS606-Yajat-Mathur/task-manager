"""Data consistency - TC-Integrity-01 (TMA-NF-004)."""

import random
from unittest import mock

from tests.helpers import APITestCase


class TestIntegrity(APITestCase):
    def test_TC_Integrity_01_repeated_crud_preserves_state(self):
        """
        60 random create / edit / complete / delete operations. We keep our own record
        (`expected`) of what the database must hold, then compare it with what the API
        returns. Any lost or half-applied change would make them differ.
        """
        h = self.new_user()
        expected = {}
        rng = random.Random(7)                       # fixed seed -> the same run every time
        for step in range(60):
            action = rng.choice(["create", "create", "update", "complete", "delete"])
            if action == "create" or not expected:
                t = self.create_task(h, title=f"task {step}", categories=["Batch"])
                expected[t["id"]] = {"title": t["title"], "status": "ACTIVE"}
            else:
                tid = rng.choice(list(expected))
                if action == "update":
                    self.client.patch(f"/api/tasks/{tid}", json={"title": f"edited {step}"},
                                      headers=h)
                    expected[tid]["title"] = f"edited {step}"
                elif action == "complete":
                    self.client.post(f"/api/tasks/{tid}/complete", headers=h)
                    expected[tid]["status"] = "COMPLETED"
                else:
                    self.client.delete(f"/api/tasks/{tid}", headers=h)
                    del expected[tid]

        actual = {t["id"]: {"title": t["title"], "status": t["status"]}
                  for t in self.list_tasks(h, "?limit=500")}
        self.assertEqual(actual, expected)
        # No orphan rows left behind by the deletes
        for table in ("task_categories", "task_history", "reminders"):
            with self.subTest(table=table):
                orphans = self.sql(f"SELECT COUNT(*) AS n FROM {table} "
                                   f"WHERE task_id NOT IN (SELECT id FROM tasks)")[0]["n"]
                self.assertEqual(orphans, 0)

    def test_failed_transaction_rolls_back(self):
        """If anything fails in the middle of a transaction, none of it is kept."""
        from app.db import transaction
        h = self.new_user()
        self.create_task(h, title="before")
        with self.app.app_context():
            with self.assertRaises(RuntimeError):
                with transaction() as db:
                    db.execute("UPDATE tasks SET title = 'half-done'")
                    raise RuntimeError("crash in the middle")
        self.assertEqual(self.list_tasks(h)[0]["title"], "before")

    def test_crash_while_saving_a_task_leaves_nothing_behind(self):
        """Task row, category links and history are one unit: all saved or none."""
        h = self.new_user()
        with mock.patch("app.tasks.set_task_categories", side_effect=RuntimeError("disk full")):
            with self.assertLogs(self.app.logger, level="ERROR"):    # expected, kept quiet
                resp = self.client.post("/api/tasks", json={"title": "x", "categories": ["A"]},
                                        headers=h)
        self.assertEqual(resp.status_code, 500)
        for table in ("tasks", "task_history", "task_categories"):
            with self.subTest(table=table):
                self.assertEqual(self.sql(f"SELECT * FROM {table}"), [])

    def test_invalid_edit_changes_nothing(self):
        h = self.new_user()
        task = self.create_task(h, title="Keep", priority="HIGH", categories=["A"])
        resp = self.client.patch(f"/api/tasks/{task['id']}", headers=h,
                                 json={"title": "New", "categories": ["B"], "dueDate": "soon"})
        self.assertEqual(resp.status_code, 400)
        fetched = self.client.get(f"/api/tasks/{task['id']}", headers=h).get_json()["task"]
        self.assertEqual((fetched["title"], fetched["categories"]), ("Keep", ["A"]))
