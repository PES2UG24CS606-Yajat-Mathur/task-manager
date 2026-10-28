"""Task priority - TC-Org-01 (TMA-F-020)."""

from tests.helpers import APITestCase


class TestPriority(APITestCase):
    def setUp(self):
        super().setUp()
        self.h = self.new_user()

    def patch(self, task_id, body):
        return self.client.patch(f"/api/tasks/{task_id}", json=body, headers=self.h)

    def test_TC_Org_01_priority_saved_and_displayed(self):
        self.assertEqual(self.create_task(self.h)["priority"], "MEDIUM")   # default
        task = self.create_task(self.h, priority="high")                  # case-insensitive
        self.assertEqual(task["priority"], "HIGH")
        self.assertEqual(self.patch(task["id"], {"priority": "LOW"}).get_json()["task"]
                         ["priority"], "LOW")
        listed = {t["id"]: t["priority"] for t in self.list_tasks(self.h)}
        self.assertEqual(listed[task["id"]], "LOW")                       # shown in the list

    def test_invalid_priority_rejected(self):
        task = self.create_task(self.h, title="Keep", priority="HIGH")
        self.assertEqual(self.patch(task["id"], {"priority": "CRITICAL"}).status_code, 400)
        resp = self.client.post("/api/tasks", json={"title": "x", "priority": 5}, headers=self.h)
        self.assertEqual(resp.status_code, 400)
        fetched = self.client.get(f"/api/tasks/{task['id']}", headers=self.h).get_json()["task"]
        self.assertEqual(fetched["priority"], "HIGH")                    # unchanged

    def test_priority_change_is_recorded_in_history(self):
        task = self.create_task(self.h)
        self.patch(task["id"], {"priority": "HIGH"})
        history = self.client.get(f"/api/tasks/{task['id']}/history",
                                  headers=self.h).get_json()["history"]
        self.assertEqual(history[-1]["details"], {"priority": "HIGH"})
