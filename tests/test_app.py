"""Project setup: application factory, database schema, JSON error handling."""

from tests.helpers import APITestCase


class TestSkeleton(APITestCase):
    def test_database_schema_created(self):
        tables = {r["name"] for r in self.sql("SELECT name FROM sqlite_master WHERE type='table'")}
        expected = {"users", "sessions", "tasks", "categories", "task_categories", "reminders",
                    "task_history", "notification_preferences", "notifications",
                    "security_events"}
        self.assertTrue(expected <= tables, expected - tables)

    def test_index_page_served(self):
        with self.client.get("/") as resp:
            self.assertEqual(resp.status_code, 200)
            self.assertIn("Task Manager", resp.get_data(as_text=True))

    def test_unknown_api_route_returns_json_404(self):
        resp = self.client.get("/api/does-not-exist")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"]["code"], "NOT_FOUND")

    def test_unexpected_errors_return_clean_json(self):
        @self.app.get("/api/boom")
        def boom():
            raise RuntimeError("internal detail")
        with self.assertLogs(self.app.logger, level="ERROR"):   # expected traceback, kept quiet
            resp = self.client.get("/api/boom")
        self.assertEqual(resp.status_code, 500)
        self.assertNotIn("internal detail", resp.get_data(as_text=True))  # no leak
        self.assertEqual(resp.get_json()["error"]["code"], "INTERNAL_ERROR")
