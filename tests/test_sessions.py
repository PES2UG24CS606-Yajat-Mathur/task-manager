"""Sessions and logout - TC-Auth-04, TC-Sec-04 (TMA-F-004, TMA-SR-004)."""

from tests.helpers import APITestCase


class TestSessions(APITestCase):
    def test_TC_Auth_02b_token_gives_access_to_protected_routes(self):
        headers = self.new_user("bob@example.com")
        resp = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["user"]["email"], "bob@example.com")

    def test_TC_Auth_04_logout_terminates_session(self):
        headers = self.new_user("erin@example.com")
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/logout", headers=headers).status_code, 200)
        # Protected pages now require re-authentication
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/logout", headers=headers).status_code, 401)

    def test_logout_only_ends_that_session(self):
        laptop = self.new_user("multi@example.com")
        phone = {"Authorization": "Bearer " + self.login("multi@example.com").get_json()
                 ["sessionToken"]}
        self.client.post("/api/auth/logout", headers=laptop)
        self.assertEqual(self.client.get("/api/auth/me", headers=phone).status_code, 200)

    def test_TC_Sec_04_expired_and_forged_tokens_rejected(self):
        headers = self.new_user("sess@example.com")
        token = headers["Authorization"].split()[1]

        # The raw token is never stored - only its SHA-256 hash
        stored = self.sql("SELECT token_hash FROM sessions")[0]["token_hash"]
        self.assertNotEqual(stored, token)
        self.assertEqual(len(stored), 64)

        # Forged / tampered token
        forged = {"Authorization": f"Bearer {token[:-2]}xx"}
        self.assertEqual(self.client.get("/api/auth/me", headers=forged).status_code, 401)

        # Expire the session in the database -> rejected
        self.sql("UPDATE sessions SET expires_at = '2000-01-01T00:00:00'")
        resp = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(resp.status_code, 401)
        self.assertIn("expired", resp.get_json()["error"]["message"])

    def test_missing_or_wrong_scheme_rejected(self):
        headers = self.new_user("scheme@example.com")
        token = headers["Authorization"].split()[1]
        self.assertEqual(self.client.get("/api/auth/me").status_code, 401)
        resp = self.client.get("/api/auth/me", headers={"Authorization": f"Basic {token}"})
        self.assertEqual(resp.status_code, 401)

    def test_deactivated_account_token_rejected(self):
        headers = self.new_user("gone@example.com")
        self.sql("UPDATE users SET is_active = 0")
        self.assertEqual(self.client.get("/api/auth/me", headers=headers).status_code, 401)

    def test_update_profile(self):
        headers = self.new_user("frank@example.com", "Frank")
        resp = self.client.patch("/api/auth/me", json={"name": "Frank B"}, headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["user"]["name"], "Frank B")
        self.new_user("taken@example.com")
        clash = self.client.patch("/api/auth/me", json={"email": "taken@example.com"},
                                  headers=headers)
        self.assertEqual(clash.status_code, 409)
