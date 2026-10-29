"""
Security event logging - TC-Sec-05 (TMA-SR-005), and the login lockout - TC-Auth-03b.
"""

import json

from app.security import _scrub, log_security_event
from tests.helpers import DEFAULT_PASSWORD, APITestCase


class TestSecurityLogging(APITestCase):
    def events(self, event_type=None):
        if event_type:
            return self.sql("SELECT * FROM security_events WHERE event_type = ? ORDER BY id",
                            (event_type,))
        return self.sql("SELECT * FROM security_events ORDER BY id")

    def test_scrubber_removes_sensitive_keys(self):
        cleaned = _scrub({"password": "x", "sessionToken": "y", "nested": {"new_password": "z"},
                          "X-Auth-Token": "t", "reason": "ok"})
        self.assertEqual(cleaned, {"nested": {}, "reason": "ok"})

    def test_TC_Sec_05_event_logged_without_secrets(self):
        with self.app.test_request_context("/api/auth/login",
                                           environ_base={"REMOTE_ADDR": "10.0.0.7"}):
            log_security_event("LOGIN_FAILED", email="a@example.com",
                               details={"reason": "invalid credentials", "password": "Hunter22",
                                        "Authorization": "Bearer abc"})
        rows = self.events()
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual((row["event_type"], row["email"], row["ip_address"]),
                         ("LOGIN_FAILED", "a@example.com", "10.0.0.7"))
        self.assertEqual(json.loads(row["details"]), {"reason": "invalid credentials"})
        self.assertNotIn("Hunter22", json.dumps(dict(row)))

    def test_failed_logins_logged_without_passwords(self):
        self.register("log@example.com")
        self.login("log@example.com", "MySecretGuess9")       # wrong password
        self.login("ghost@example.com", "AnotherGuess1")      # no such account
        failed = self.events("LOGIN_FAILED")
        self.assertEqual([r["email"] for r in failed], ["log@example.com", "ghost@example.com"])
        # No password, attempted or real, anywhere in the security log
        everything = json.dumps([dict(r) for r in self.events()])
        for secret in ("MySecretGuess9", "AnotherGuess1", DEFAULT_PASSWORD):
            self.assertNotIn(secret, everything)

    def test_account_lifecycle_is_logged(self):
        headers = self.new_user("life@example.com")              # REGISTER + LOGIN_SUCCESS
        self.client.post("/api/auth/logout", headers=headers)   # LOGOUT
        self.assertEqual([r["event_type"] for r in self.events()],
                         ["REGISTER", "LOGIN_SUCCESS", "LOGOUT"])

    def test_access_denied_is_logged(self):
        owner, intruder = self.new_user("owner@example.com"), self.new_user("bad@example.com")
        task = self.create_task(owner)
        self.client.get(f"/api/tasks/{task['id']}", headers=intruder)
        denied = self.events("ACCESS_DENIED")
        self.assertEqual(len(denied), 1)
        self.assertEqual(json.loads(denied[0]["details"])["reason"], "not task owner")


class TestLoginLockout(APITestCase):
    def test_TC_Auth_03b_repeated_failures_are_rate_limited(self):
        self.register("dave@example.com")
        for _ in range(self.app.config["MAX_FAILED_LOGINS"]):
            self.assertEqual(self.login("dave@example.com", "WrongPass1").status_code, 401)
        # Even the right password is refused while the account is cooling down
        blocked = self.login("dave@example.com")
        self.assertEqual(blocked.status_code, 429)
        self.assertIn("Too many failed attempts", blocked.get_json()["error"]["message"])
        self.assertEqual(len(self.sql("SELECT * FROM security_events "
                                      "WHERE event_type = 'LOGIN_BLOCKED'")), 1)
        # Other accounts are not affected
        self.register("erin@example.com")
        self.assertEqual(self.login("erin@example.com").status_code, 200)

    def test_lockout_ends_when_the_window_passes(self):
        self.register("fay@example.com")
        for _ in range(self.app.config["MAX_FAILED_LOGINS"]):
            self.login("fay@example.com", "WrongPass1")
        self.assertEqual(self.login("fay@example.com").status_code, 429)
        # Move the failures 20 minutes into the past (the window is 15 minutes)
        self.sql("UPDATE security_events SET created_at = '2000-01-01T00:00:00'")
        self.assertEqual(self.login("fay@example.com").status_code, 200)
