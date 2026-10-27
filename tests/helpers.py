"""
Shared test fixtures.

Tests are written as `unittest.TestCase` classes so they run with BOTH
    pytest                         (used in CI, gives coverage + JUnit report)
    python -m unittest discover    (needs nothing installed beyond Flask)

Every test gets a brand-new temporary SQLite database, so tests never affect each
other or your real data. Test names carry the STP test-case IDs (e.g. TC-Auth-01)
so the CI report doubles as test-execution evidence for the RTM.
"""

import os
import shutil
import sqlite3
import tempfile
import unittest

from app import create_app

DEFAULT_PASSWORD = "Passw0rd1"


class APITestCase(unittest.TestCase):
    config_overrides = {}          # subclasses can change config (e.g. FORCE_HTTPS)

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="tm-test-")
        self.db_path = os.path.join(self.tmpdir, "test.sqlite3")
        self.app = create_app("testing", {"DATABASE": self.db_path, **self.config_overrides})
        self.client = self.app.test_client()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ------------------------------------------------------------- helpers
    def register(self, email="user@example.com", name="Test User", password=DEFAULT_PASSWORD):
        return self.client.post("/api/auth/register",
                                json={"name": name, "email": email, "password": password})

    def login(self, email="user@example.com", password=DEFAULT_PASSWORD):
        return self.client.post("/api/auth/login", json={"email": email, "password": password})

    def new_user(self, email="user@example.com", name="Test User", admin=False) -> dict:
        """Register + log in; return the Authorization header dict for that user."""
        self.assertEqual(self.register(email, name).status_code, 201)
        if admin:
            self.sql("UPDATE users SET role = 'admin' WHERE email = ?", (email,))
        token = self.login(email).get_json()["sessionToken"]
        return {"Authorization": f"Bearer {token}"}

    def create_task(self, headers, **fields) -> dict:
        body = {"title": "A task", **fields}
        resp = self.client.post("/api/tasks", json=body, headers=headers)
        self.assertEqual(resp.status_code, 201, resp.get_json())
        return resp.get_json()["task"]

    def list_tasks(self, headers, query="") -> list:
        resp = self.client.get(f"/api/tasks{query}", headers=headers)
        self.assertEqual(resp.status_code, 200, resp.get_json())
        return resp.get_json()["tasks"]

    def sql(self, statement, params=()):
        """Run SQL directly against the test database (for inspection / setup)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(statement, params).fetchall()
            conn.commit()
            return rows
        finally:
            conn.close()
