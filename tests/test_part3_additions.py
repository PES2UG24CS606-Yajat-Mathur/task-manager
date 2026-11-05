"""
Tests added in Mini-Project Part 3 (2-6 Nov 2026). The Part 3 coverage measurement showed which
code no test had run; these tests close those gaps. They exercise real paths through the
application: the command-line tools, the background reminder thread, the e-mail channel and
the less common validation branches.

The last class pins the fixes for defects found by system validation of v1.0 (DEF-01 to DEF-04).
They were expected failures until Sprint 3 fixed them in v1.0.1; test_input_robustness.py
extends the same checks to every route.
"""

import threading
from unittest import mock

from app.db import get_db
from app.notifications import email_notifier, process_due_reminders, start_reminder_scheduler
from app.security import create_session, revoke_all_sessions
from app.tasks import task_to_dict
from app.utils import parse_client_datetime
from tests.helpers import APITestCase, DEFAULT_PASSWORD


def add_due_reminder(case, headers):
    """Create a task with a reminder that is already due (written directly: the API refuses the past)."""
    task = case.create_task(headers, title="Due now")
    case.sql("INSERT INTO reminders (task_id, reminder_time) VALUES (?, '2000-01-01T00:00:00')",
             (task["id"],))
    return task


class TestCommandLineTools(APITestCase):
    def cli(self, *args):
        return self.app.test_cli_runner().invoke(args=list(args))

    def test_TC_Admin_01b_create_admin_command_reports_invalid_input(self):
        result = self.cli("create-admin", "--name", "Root", "--email", "not-an-email",
                          "--password", DEFAULT_PASSWORD)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("valid email", result.output)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM users")[0]["n"], 0)

    def test_TC_Integrity_01b_init_db_command_is_safe_to_repeat(self):
        headers = self.new_user()
        self.create_task(headers, title="Keep me")
        result = self.cli("init-db")
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Initialised database", result.output)
        self.assertEqual(self.list_tasks(headers)[0]["title"], "Keep me")


class TestReminderScheduler(APITestCase):
    def run_one_pass(self):
        """
        Run the real background thread for one iteration of its endless loop. The patched
        time.sleep tells us the pass has finished, then parks the daemon thread for good.
        """
        pass_finished, parked = threading.Event(), threading.Event()

        def fake_sleep(_seconds):
            pass_finished.set()
            parked.wait()

        with mock.patch("app.notifications.time.sleep", fake_sleep):
            start_reminder_scheduler(self.app)
            self.assertTrue(pass_finished.wait(timeout=10), "scheduler did not finish a pass")

    def test_TC_Notify_01b_background_thread_delivers_due_reminders(self):
        task = add_due_reminder(self, self.new_user())
        self.run_one_pass()
        rows = self.sql("SELECT * FROM notifications WHERE task_id = ?", (task["id"],))
        self.assertEqual(len(rows), 1)

    def test_TC_Notify_01d_background_thread_pass_with_nothing_due(self):
        self.new_user()
        self.run_one_pass()
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM notifications")[0]["n"], 0)

    def test_TC_Notify_01c_background_thread_survives_a_failed_pass(self):
        failing = mock.patch("app.notifications.process_due_reminders", side_effect=RuntimeError("boom"))
        with failing, self.assertLogs(self.app.logger, level="ERROR") as logs:
            self.run_one_pass()
        self.assertIn("Reminder scheduler iteration failed", logs.output[0])


class TestEmailChannel(APITestCase):
    """The e-mail provider is a stub, so it is tested at the interface only (Test Plan section 4)."""

    def deliver_with_email_on(self):
        headers = self.new_user()
        self.client.put("/api/preferences", json={"notifications": {"email": True}}, headers=headers)
        task = add_due_reminder(self, headers)
        with self.app.app_context():
            created = process_due_reminders()
        return task, created

    def test_TC_Notify_01e_email_not_sent_when_the_service_is_disabled(self):
        task, created = self.deliver_with_email_on()
        channels = [r["channel"] for r in self.sql("SELECT channel FROM notifications WHERE task_id = ?",
                                                   (task["id"],))]
        self.assertEqual((created, channels), (1, ["in_app"]))

    def test_TC_Notify_01f_email_handed_to_the_service_when_enabled(self):
        self.app.config["EMAIL_NOTIFICATIONS_ENABLED"] = True
        task, created = self.deliver_with_email_on()
        channels = {r["channel"] for r in self.sql("SELECT channel FROM notifications WHERE task_id = ?",
                                                   (task["id"],))}
        self.assertEqual((created, channels), (2, {"in_app", "email"}))

    def test_TC_Notify_01g_email_interface_returns_whether_it_was_sent(self):
        with self.app.app_context():
            self.assertFalse(email_notifier.send("a@b.co", "Subject", "Body"))
            self.app.config["EMAIL_NOTIFICATIONS_ENABLED"] = True
            self.assertTrue(email_notifier.send("a@b.co", "Subject", "Body"))


class TestNotificationsAndAdminRoutes(APITestCase):
    def test_TC_Notify_01i_mark_all_as_read(self):
        headers = self.new_user()
        add_due_reminder(self, headers)
        add_due_reminder(self, headers)
        self.assertEqual(self.client.get("/api/notifications", headers=headers).get_json()["unread"], 2)
        self.assertEqual(self.client.post("/api/notifications/read-all", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/api/notifications", headers=headers).get_json()["unread"], 0)

    def test_TC_Sec_05c_admin_reads_all_events_and_bad_limit_is_refused(self):
        admin = self.new_user("root@example.com", admin=True)
        events = self.client.get("/api/admin/security-events", headers=admin)
        self.assertEqual(events.status_code, 200)
        self.assertGreaterEqual(len(events.get_json()["events"]), 2)   # REGISTER and LOGIN_SUCCESS
        bad_limit = self.client.get("/api/admin/security-events?limit=abc", headers=admin)
        self.assertEqual(bad_limit.status_code, 400)


class TestValidationBranches(APITestCase):
    def assert_field_error(self, resp, field):
        self.assertEqual(resp.status_code, 400, resp.get_json())
        self.assertEqual(resp.get_json()["error"]["details"]["field"], field)

    def test_TC_Auth_01c_name_longer_than_100_characters_refused(self):
        self.assert_field_error(self.register(name="x" * 101), "name")

    def test_TC_Task_01c_description_must_be_text_of_limited_length(self):
        headers = self.new_user()
        for bad in (42, "x" * 2001):
            with self.subTest(description=str(bad)[:10]):
                resp = self.client.post("/api/tasks", headers=headers,
                                        json={"title": "t", "description": bad})
                self.assert_field_error(resp, "description")

    def test_TC_Org_03b_blank_category_names_are_dropped(self):
        task = self.create_task(self.new_user(), categories=["  ", "Home", ""])
        self.assertEqual(task["categories"], ["Home"])

    def test_TC_Task_02c_patch_without_real_change_writes_nothing(self):
        headers = self.new_user()
        task = self.create_task(headers, title="Same")
        resp = self.client.patch(f"/api/tasks/{task['id']}", json={"title": "Same"}, headers=headers)
        self.assertEqual(resp.status_code, 200)
        changes = self.sql("SELECT COUNT(*) AS n FROM task_history WHERE task_id = ?", (task["id"],))[0]["n"]
        self.assertEqual(changes, 1)     # only the CREATED entry

    def test_TC_Org_04b_time_without_offset_is_taken_as_utc(self):
        self.assertEqual(parse_client_datetime("2030-01-02T03:04:05").isoformat(), "2030-01-02T03:04:05")

    def test_TC_UX_01b_unknown_page_keeps_the_normal_not_found_page(self):
        resp = self.client.get("/no-such-page")
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("application/json", resp.content_type)


class TestInternalHelpers(APITestCase):
    def test_TC_Sec_04b_revoke_all_sessions_without_a_caller_transaction(self):
        headers = self.new_user()
        user_id = self.sql("SELECT id FROM users")[0]["id"]
        with self.app.app_context():
            create_session(user_id)
            revoke_all_sessions(user_id)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM sessions WHERE revoked_at IS NULL")[0]["n"], 0)
        self.assertEqual(self.client.get("/api/tasks", headers=headers).status_code, 401)

    def test_TC_Task_01d_plain_task_row_falls_back_to_the_stored_status(self):
        self.create_task(self.new_user(), title="Plain")
        with self.app.app_context():
            row = get_db().execute("SELECT * FROM tasks").fetchone()
            self.assertEqual(task_to_dict(row)["status"], "ACTIVE")


class TestDefectsFoundBySystemValidation(APITestCase):
    """Regression tests for defects fixed in Sprint 3. See the module docstring."""

    def assert_client_error(self, resp):
        self.assertLess(resp.status_code, 500, resp.get_json())

    def test_DEF_01_huge_integer_in_url_or_query_is_not_a_server_error(self):
        headers = self.new_user()
        self.assert_client_error(self.client.get(f"/api/tasks/{10 ** 20}", headers=headers))

    def test_DEF_02_date_outside_the_supported_range_is_not_a_server_error(self):
        resp = self.client.post("/api/tasks", headers=self.new_user(),
                                json={"title": "t", "dueDate": "0001-01-01T00:00:00+05:30"})
        self.assert_client_error(resp)

    def test_DEF_03_infinite_minutes_before_is_not_a_server_error(self):
        headers = self.new_user()
        task = self.create_task(headers, dueDate="2030-01-01")
        resp = self.client.post(f"/api/tasks/{task['id']}/reminders", headers=headers,
                                data='{"minutesBefore": 1e999}', content_type="application/json")
        self.assert_client_error(resp)

    def test_DEF_04_lone_surrogate_in_text_is_not_a_server_error(self):
        resp = self.client.post("/api/tasks", headers=self.new_user(), data='{"title": "\\ud800"}',
                                content_type="application/json")
        self.assert_client_error(resp)
