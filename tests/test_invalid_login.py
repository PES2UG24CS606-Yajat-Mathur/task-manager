"""Invalid login rejection - TC-Auth-03 (TMA-F-003)."""

from unittest import mock

from tests.helpers import APITestCase


class TestInvalidLogin(APITestCase):
    def test_TC_Auth_03_invalid_credentials_rejected(self):
        self.register("carol@example.com")
        wrong_pw = self.login("carol@example.com", "WrongPass1")
        no_user = self.login("nobody@example.com", "WrongPass1")
        for resp in (wrong_pw, no_user):
            self.assertEqual(resp.status_code, 401)
            self.assertNotIn("sessionToken", resp.get_json())
            # Same message in both cases -> an attacker cannot tell which emails exist
            self.assertEqual(resp.get_json()["error"]["message"], "Invalid email or password")
        self.assertEqual(len(self.sql("SELECT * FROM sessions")), 0)   # no session created

    def test_unknown_email_still_checks_a_password_hash(self):
        """Equal work for both failure cases, so response time does not leak anything."""
        with mock.patch("app.auth.verify_password", return_value=False) as verify:
            self.login("ghost@example.com", "WrongPass1")
        verify.assert_called_once()

    def test_deactivated_account_cannot_log_in(self):
        self.register("dora@example.com")
        self.sql("UPDATE users SET is_active = 0")
        resp = self.login("dora@example.com")
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(len(self.sql("SELECT * FROM sessions")), 0)
