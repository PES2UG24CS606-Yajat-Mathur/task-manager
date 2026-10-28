"""Registration and login - TC-Auth-01, TC-Auth-02 (TMA-F-001, TMA-F-002)."""

from tests.helpers import APITestCase


class TestRegistration(APITestCase):
    def test_TC_Auth_01_register_creates_unique_account(self):
        resp = self.register("alice@example.com", "Alice")
        self.assertEqual(resp.status_code, 201)
        user = resp.get_json()["user"]
        self.assertEqual(user["email"], "alice@example.com")
        self.assertNotIn("passwordHash", user)            # hash is never returned

        # Same email again (different case) -> rejected, still exactly one account
        dup = self.register("ALICE@example.com", "Alice 2")
        self.assertEqual(dup.status_code, 409)
        self.assertEqual(len(self.sql("SELECT * FROM users")), 1)

    def test_TC_Auth_01b_register_validates_input(self):
        cases = [
            ({"name": "", "email": "a@b.com", "password": "Passw0rd1"}, "name"),
            ({"name": "A", "email": "not-an-email", "password": "Passw0rd1"}, "email"),
            ({"name": "A", "email": "a@b.com", "password": "short1"}, "password"),
            ({"name": "A", "email": "a@b.com", "password": "lettersonly"}, "password"),
        ]
        for body, field in cases:
            with self.subTest(field=field, body=body):
                resp = self.client.post("/api/auth/register", json=body)
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.get_json()["error"]["details"]["field"], field)
        self.assertEqual(self.sql("SELECT * FROM users"), [])     # nothing half-created

    def test_register_rejects_non_json_body(self):
        resp = self.client.post("/api/auth/register", data="hello")
        self.assertEqual(resp.status_code, 400)


class TestLogin(APITestCase):
    def test_TC_Auth_02_valid_login_returns_session_token(self):
        self.register("bob@example.com")
        resp = self.login("bob@example.com")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["sessionToken"])
        self.assertEqual(data["user"]["email"], "bob@example.com")
        self.assertEqual(len(self.sql("SELECT * FROM sessions")), 1)

    def test_login_email_is_case_insensitive(self):
        self.register("carol@example.com")
        self.assertEqual(self.login("CAROL@Example.com").status_code, 200)

    def test_login_requires_both_fields(self):
        resp = self.client.post("/api/auth/login", json={"email": "x@example.com"})
        self.assertEqual(resp.status_code, 400)
