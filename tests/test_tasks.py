"""Task Module - create, view, edit: TC-Task-01..02 (TMA-F-010, TMA-F-011)."""

from tests.helpers import APITestCase


class TestTaskCrud(APITestCase):
    def setUp(self):
        super().setUp()
        self.h = self.new_user()

    def test_TC_Task_01_create_task_appears_in_list(self):
        task = self.create_task(self.h, title="Write SAD", description="Section 3")
        self.assertEqual(task["title"], "Write SAD")
        self.assertEqual(task["description"], "Section 3")
        self.assertEqual(task["status"], "ACTIVE")
        titles = [t["title"] for t in self.list_tasks(self.h)]
        self.assertIn("Write SAD", titles)

    def test_TC_Task_01b_create_requires_title(self):
        for body in ({}, {"title": ""}, {"title": "   "}, {"title": "x" * 201}):
            with self.subTest(body=str(body)[:30]):
                resp = self.client.post("/api/tasks", json=body, headers=self.h)
                self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.list_tasks(self.h), [])

    def test_TC_Task_02_edit_task(self):
        task = self.create_task(self.h, title="Draft")
        resp = self.client.patch(f"/api/tasks/{task['id']}",
                                 json={"title": "Final", "description": "Updated"}, headers=self.h)
        self.assertEqual(resp.status_code, 200)
        fetched = self.client.get(f"/api/tasks/{task['id']}", headers=self.h).get_json()["task"]
        self.assertEqual((fetched["title"], fetched["description"]), ("Final", "Updated"))

    def test_TC_Task_02b_invalid_field_rejects_whole_update(self):
        task = self.create_task(self.h, title="Keep me")
        resp = self.client.patch(f"/api/tasks/{task['id']}",
                                 json={"description": "Changed", "title": ""}, headers=self.h)
        self.assertEqual(resp.status_code, 400)
        fetched = self.client.get(f"/api/tasks/{task['id']}", headers=self.h).get_json()["task"]
        self.assertEqual((fetched["title"], fetched["description"]), ("Keep me", ""))  # untouched

    def test_missing_task_returns_404(self):
        self.assertEqual(self.client.get("/api/tasks/999", headers=self.h).status_code, 404)

    def test_unknown_fields_rejected(self):
        task = self.create_task(self.h)
        resp = self.client.patch(f"/api/tasks/{task['id']}", json={"user_id": 2}, headers=self.h)
        self.assertEqual(resp.status_code, 400)

    def test_task_routes_require_login(self):
        self.assertEqual(self.client.get("/api/tasks").status_code, 401)
        self.assertEqual(self.client.post("/api/tasks", json={"title": "x"}).status_code, 401)
