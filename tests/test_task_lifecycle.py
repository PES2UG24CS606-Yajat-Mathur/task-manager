"""Task Module - delete and complete/reopen: TC-Task-03..04 (TMA-F-012, TMA-F-013)."""

from tests.helpers import APITestCase


class TestTaskLifecycle(APITestCase):
    def setUp(self):
        super().setUp()
        self.h = self.new_user()

    def test_TC_Task_03_delete_task(self):
        task = self.create_task(self.h, title="Temporary")
        self.assertEqual(self.client.delete(f"/api/tasks/{task['id']}", headers=self.h).status_code,
                         200)
        self.assertEqual(self.client.get(f"/api/tasks/{task['id']}", headers=self.h).status_code,
                         404)
        self.assertEqual(self.list_tasks(self.h), [])
        self.assertEqual(self.sql("SELECT * FROM task_history"), [])   # cascade, no orphans

    def test_delete_missing_task_returns_404(self):
        self.assertEqual(self.client.delete("/api/tasks/404", headers=self.h).status_code, 404)

    def test_TC_Task_04_complete_and_reopen(self):
        task = self.create_task(self.h)
        done = self.client.post(f"/api/tasks/{task['id']}/complete", headers=self.h).get_json()
        self.assertEqual(done["task"]["status"], "COMPLETED")
        self.assertIsNotNone(done["task"]["completedAt"])
        again = self.client.post(f"/api/tasks/{task['id']}/reopen", headers=self.h).get_json()
        self.assertEqual(again["task"]["status"], "ACTIVE")
        self.assertIsNone(again["task"]["completedAt"])

        history = self.client.get(f"/api/tasks/{task['id']}/history",
                                  headers=self.h).get_json()["history"]
        self.assertEqual([h["changeType"] for h in history], ["CREATED", "COMPLETED", "REOPENED"])

    def test_completing_twice_is_harmless(self):
        task = self.create_task(self.h)
        for _ in range(2):
            self.client.post(f"/api/tasks/{task['id']}/complete", headers=self.h)
        history = self.client.get(f"/api/tasks/{task['id']}/history",
                                  headers=self.h).get_json()["history"]
        self.assertEqual(len(history), 2)                         # CREATED + one COMPLETED
