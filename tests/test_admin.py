"""Administration - TC-Admin-01 (TMA-F-042), admin actions logged - TC-Sec-05b (TMA-SR-005)."""

from tests.helpers import APITestCase


class TestAdmin(APITestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.new_user("admin@example.com", "Admin", admin=True)
        self.member = self.new_user("member@example.com", "Member")
        self.member_id = self.user_id("member@example.com")
        self.admin_id = self.user_id("admin@example.com")

    def user_id(self, email):
        return self.sql("SELECT id FROM users WHERE email = ?", (email,))[0]["id"]

    def patch_user(self, user_id, body, headers=None):
        return self.client.patch(f"/api/admin/users/{user_id}", json=body,
                                 headers=headers or self.admin)

    def test_TC_Admin_01_only_admins_can_manage_users(self):
        for method, path in [("get", "/api/admin/users"), ("get", "/api/admin/security-events"),
                             ("patch", f"/api/admin/users/{self.admin_id}"),
                             ("delete", f"/api/admin/users/{self.admin_id}")]:
            with self.subTest(path=path, method=method):
                kwargs = {"json": {"role": "user"}} if method == "patch" else {}
                resp = getattr(self.client, method)(path, headers=self.member, **kwargs)
                self.assertEqual(resp.status_code, 403)                     # normal user: no
                self.assertEqual(getattr(self.client, method)(path, **kwargs).status_code, 401)
        users = self.client.get("/api/admin/users", headers=self.admin).get_json()["users"]
        self.assertEqual({u["email"] for u in users}, {"admin@example.com", "member@example.com"})
        self.assertTrue(all("password" not in str(u).lower() for u in users))

    def test_deactivation_logs_the_user_out_and_blocks_login(self):
        self.assertEqual(self.patch_user(self.member_id, {"isActive": False}).status_code, 200)
        self.assertEqual(self.client.get("/api/tasks", headers=self.member).status_code, 401)
        self.assertEqual(self.login("member@example.com").status_code, 403)
        # Reactivated -> can log in again
        self.patch_user(self.member_id, {"isActive": True})
        self.assertEqual(self.login("member@example.com").status_code, 200)

    def test_admin_cannot_lock_themselves_out(self):
        for body in ({"isActive": False}, {"role": "user"}):
            with self.subTest(body=body):
                self.assertEqual(self.patch_user(self.admin_id, body).status_code, 400)
        self.assertEqual(self.client.delete(f"/api/admin/users/{self.admin_id}",
                                            headers=self.admin).status_code, 400)

    def test_invalid_admin_updates_rejected(self):
        for body in ({}, {"role": "root"}, {"isActive": "no"}):
            with self.subTest(body=body):
                self.assertEqual(self.patch_user(self.member_id, body).status_code, 400)
        self.assertEqual(self.patch_user(9999, {"role": "admin"}).status_code, 404)

    def test_promote_and_delete_user(self):
        promoted = self.patch_user(self.member_id, {"role": "admin"}).get_json()["user"]
        self.assertEqual(promoted["role"], "admin")
        self.create_task(self.member, title="member task")
        self.assertEqual(self.client.delete(f"/api/admin/users/{self.member_id}",
                                            headers=self.admin).status_code, 200)
        self.assertEqual(self.sql("SELECT * FROM tasks"), [])          # their data went too

    def test_security_events_review(self):
        self.login("member@example.com", "WrongPass1")
        events = self.client.get("/api/admin/security-events?type=LOGIN_FAILED",
                                 headers=self.admin).get_json()["events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["email"], "member@example.com")

    def test_TC_Sec_05b_admin_actions_logged(self):
        self.patch_user(self.member_id, {"isActive": False})
        self.client.delete(f"/api/admin/users/{self.member_id}", headers=self.admin)
        types = [r["event_type"] for r in self.sql("SELECT event_type FROM security_events")]
        self.assertIn("ADMIN_UPDATE_USER", types)
        self.assertIn("ADMIN_DELETE_USER", types)

    def test_create_admin_cli(self):
        runner = self.app.test_cli_runner()
        result = runner.invoke(args=["create-admin", "--name", "Root", "--email",
                                     "root@example.com", "--password", "Sup3rSecret"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertEqual(self.sql("SELECT role FROM users WHERE email = 'root@example.com'")[0]
                         ["role"], "admin")
        # Weak password -> clear error, no account
        weak = runner.invoke(args=["create-admin", "--name", "X", "--email", "x@example.com",
                                   "--password", "short"])
        self.assertNotEqual(weak.exit_code, 0)
        self.assertEqual(self.sql("SELECT * FROM users WHERE email = 'x@example.com'"), [])
