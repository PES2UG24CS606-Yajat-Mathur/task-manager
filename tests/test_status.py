"""Task status, including the automatic OVERDUE status - TC-Org-02 (TMA-F-021)."""

from tests.helpers import APITestCase

PAST, FUTURE = "2020-01-01T00:00:00Z", "2099-01-01T00:00:00Z"


class TestStatus(APITestCase):
    def setUp(self):
        super().setUp()
        self.h = self.new_user()

    def patch(self, task_id, body):
        return self.client.patch(f"/api/tasks/{task_id}", json=body, headers=self.h)

    def test_TC_Org_02_status_assigned_and_updated(self):
        task = self.create_task(self.h)
        self.assertEqual(task["status"], "ACTIVE")                         # default
        done = self.patch(task["id"], {"status": "completed"}).get_json()["task"]
        self.assertEqual(done["status"], "COMPLETED")                      # case-insensitive
        self.assertIsNotNone(done["completedAt"])
        active = self.patch(task["id"], {"status": "ACTIVE"}).get_json()["task"]
        self.assertEqual(active["status"], "ACTIVE")
        self.assertIsNone(active["completedAt"])                           # kept consistent
        # A task can also be created already completed
        self.assertEqual(self.create_task(self.h, status="COMPLETED")["status"], "COMPLETED")

    def test_overdue_is_derived_from_the_due_date(self):
        late = self.create_task(self.h, title="Late", dueDate=PAST)
        self.assertEqual(late["status"], "OVERDUE")
        self.assertTrue(late["isOverdue"])
        self.assertEqual(self.sql("SELECT status FROM tasks WHERE id = ?", (late["id"],))[0]
                         ["status"], "ACTIVE")                             # stored as ACTIVE
        # Moving the due date into the future makes it ACTIVE again, with no extra step
        moved = self.patch(late["id"], {"dueDate": FUTURE}).get_json()["task"]
        self.assertEqual(moved["status"], "ACTIVE")
        # Completing an overdue task makes it COMPLETED, not OVERDUE
        self.patch(late["id"], {"dueDate": PAST})
        done = self.client.post(f"/api/tasks/{late['id']}/complete", headers=self.h).get_json()
        self.assertEqual(done["task"]["status"], "COMPLETED")

    def test_overdue_cannot_be_set_by_hand(self):
        task = self.create_task(self.h)
        for bad in ("OVERDUE", "DONE", "", 3):
            with self.subTest(bad=bad):
                self.assertEqual(self.patch(task["id"], {"status": bad}).status_code, 400)
        self.assertEqual(self.client.post("/api/tasks", json={"title": "x", "status": "OVERDUE"},
                                          headers=self.h).status_code, 400)

    def test_status_change_is_logged_in_history(self):
        task = self.create_task(self.h)
        self.patch(task["id"], {"status": "COMPLETED"})
        self.patch(task["id"], {"status": "ACTIVE"})
        history = self.client.get(f"/api/tasks/{task['id']}/history",
                                  headers=self.h).get_json()["history"]
        self.assertEqual([h["changeType"] for h in history], ["CREATED", "COMPLETED", "REOPENED"])
