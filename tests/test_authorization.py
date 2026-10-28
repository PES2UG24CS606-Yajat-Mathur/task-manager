"""Server-side authorization - TC-Sec-01 (TMA-SR-003)."""

from app.security import admin_required
from tests.helpers import APITestCase

# The only API endpoints that may be called without logging in.
PUBLIC_ENDPOINTS = {"/api/auth/register", "/api/auth/login"}


class TestEveryEndpointIsProtected(APITestCase):
    def test_TC_Sec_01b_all_api_routes_require_login(self):
        """
        Walk Flask's URL map, call every /api route WITHOUT a token, expect 401.
        A new endpoint that forgets @login_required makes this test fail.
        """
        checked = 0
        for rule in self.app.url_map.iter_rules():
            if not rule.rule.startswith("/api/") or rule.rule in PUBLIC_ENDPOINTS:
                continue
            url = rule.rule
            for arg in rule.arguments:                     # /api/tasks/<int:task_id> -> /1
                url = url.replace(f"<int:{arg}>", "1").replace(f"<{arg}>", "1")
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                with self.subTest(method=method, url=url):
                    resp = self.client.open(url, method=method, json={})
                    self.assertEqual(resp.status_code, 401)
                    checked += 1
        self.assertGreaterEqual(checked, 8)                # sanity: the walk found the routes

    def test_public_endpoints_stay_public(self):
        self.assertNotEqual(self.client.post("/api/auth/login", json={}).status_code, 401)


class TestAdminRole(APITestCase):
    def setUp(self):
        super().setUp()

        @self.app.get("/api/test-admin-only")
        @admin_required
        def admin_only():
            return {"ok": True}

    def test_admin_required_checks_role(self):
        user = self.new_user("user@example.com")
        admin = self.new_user("admin@example.com", admin=True)
        self.assertEqual(self.client.get("/api/test-admin-only").status_code, 401)
        self.assertEqual(self.client.get("/api/test-admin-only", headers=user).status_code, 403)
        self.assertEqual(self.client.get("/api/test-admin-only", headers=admin).status_code, 200)
