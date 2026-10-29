"""Availability support - TC-Reliability-01 (TMA-NF-002)."""

from tests.helpers import APITestCase


class TestHealth(APITestCase):
    def test_TC_Reliability_01_health_endpoint(self):
        resp = self.client.get("/api/health")              # no login needed
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual((body["status"], body["database"]), ("ok", "ok"))
        self.assertTrue(body["time"].endswith("Z"))

    def test_health_reports_database_failure(self):
        self.app.config["DATABASE"] = "/nonexistent-dir/x/y.sqlite3"   # cannot be opened
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 503)                 # monitors count this as "down"
        self.assertEqual(resp.get_json()["database"], "unavailable")

    def test_health_reveals_nothing_private(self):
        self.new_user("secret@example.com")
        text = self.client.get("/api/health").get_data(as_text=True)
        self.assertNotIn("secret@example.com", text)
        self.assertEqual(set(self.client.get("/api/health").get_json()),
                         {"status", "database", "time"})

    def test_app_recovers_after_restart(self):
        """Data is on disk: a new app instance on the same database sees the same tasks."""
        h = self.new_user()
        self.create_task(h, title="survives a restart")
        from app import create_app
        restarted = create_app("testing", {"DATABASE": self.db_path}).test_client()
        resp = restarted.get("/api/tasks", headers=h)
        self.assertEqual([t["title"] for t in resp.get_json()["tasks"]], ["survives a restart"])
