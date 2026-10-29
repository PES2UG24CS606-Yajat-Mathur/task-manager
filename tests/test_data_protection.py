"""
Protection of passwords and user / task data - TC-Sec-02b (TMA-NF-003).
(TC-Sec-02, passwords stored only as hashes, is in test_passwords.py.)
"""

import json

from tests.helpers import APITestCase


class TestDataProtection(APITestCase):
    def test_TC_Sec_02b_security_headers_present(self):
        for path in ("/", "/api/tasks", "/static/app.js"):
            with self.subTest(path=path), self.client.get(path) as resp:
                self.assertEqual(resp.headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(resp.headers["X-Frame-Options"], "DENY")
                self.assertEqual(resp.headers["Referrer-Policy"], "no-referrer")
                csp = resp.headers["Content-Security-Policy"]
                self.assertIn("default-src 'self'", csp)
                self.assertIn("script-src 'self'", csp)          # no inline / foreign scripts

    def test_api_responses_are_never_cached(self):
        h = self.new_user()
        self.assertEqual(self.client.get("/api/tasks", headers=h).headers["Cache-Control"],
                         "no-store")

    def test_password_hash_never_leaves_the_server(self):
        h = self.new_user("me@example.com")
        responses = [self.register("again@example.com"), self.login("me@example.com"),
                     self.client.get("/api/auth/me", headers=h)]
        for resp in responses:
            body = json.dumps(resp.get_json())
            self.assertNotIn("password", body.lower())
            self.assertNotIn("scrypt", body)
            self.assertNotIn("pbkdf2", body)

    def test_search_input_cannot_inject_sql(self):
        owner, other = self.new_user("owner@example.com"), self.new_user("other@example.com")
        self.create_task(owner, title="Owner's private task")
        for attack in ("' OR '1'='1", "x' UNION SELECT * FROM users --", "%' --"):
            with self.subTest(attack=attack):
                resp = self.client.get("/api/tasks", query_string={"q": attack}, headers=other)
                self.assertEqual(resp.status_code, 200)
                self.assertEqual(resp.get_json()["tasks"], [])       # nothing leaked
        self.assertEqual(len(self.sql("SELECT * FROM users")), 2)    # nothing dropped

    def test_html_in_task_text_is_stored_as_plain_text(self):
        """The API returns it unchanged; the UI shows it with textContent, never innerHTML."""
        h = self.new_user()
        title = "<script>alert('x')</script>"
        self.assertEqual(self.create_task(h, title=title)["title"], title)
        with self.client.get("/static/app.js") as resp:
            self.assertNotIn(".innerHTML", resp.get_data(as_text=True))
