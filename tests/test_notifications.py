"""
Notifications and preferences - TC-Notify-01, TC-Notify-02 (TMA-F-040, TMA-F-041),
and reminder delivery - TC-Org-05b (TMA-F-024).
"""

from datetime import timedelta

from app.notifications import process_due_reminders
from app.utils import to_db, utcnow
from tests.helpers import APITestCase


def soon(minutes):
    return to_db(utcnow() + timedelta(minutes=minutes)) + "Z"


class TestNotifications(APITestCase):
    def setUp(self):
        super().setUp()
        self.h = self.new_user()

    def fire_all(self):
        """Pretend it is one day later and deliver every reminder that is due by then."""
        with self.app.app_context():
            return process_due_reminders(now=to_db(utcnow() + timedelta(days=1)))

    def test_TC_Notify_01_notification_generated_for_due_reminder(self):
        task = self.create_task(self.h, title="Lab viva", dueDate=soon(60), minutesBefore=30)
        self.assertEqual(self.fire_all(), 1)
        data = self.client.get("/api/notifications", headers=self.h).get_json()
        self.assertEqual(data["unread"], 1)
        note = data["notifications"][0]
        self.assertIn("Lab viva", note["message"])
        self.assertEqual(note["taskId"], task["id"])
        self.assertIsNotNone(note["taskDueDate"])

        self.client.post(f"/api/notifications/{note['id']}/read", headers=self.h)
        self.assertEqual(self.client.get("/api/notifications?unread=true", headers=self.h)
                         .get_json()["notifications"], [])

    def test_TC_Org_05b_reminder_triggered_once_at_its_time(self):
        task = self.create_task(self.h, title="Viva", dueDate=soon(120), minutesBefore=30)
        self.client.post(f"/api/tasks/{task['id']}/reminders",
                         json={"reminderTime": soon(10)}, headers=self.h)
        with self.app.app_context():
            self.assertEqual(process_due_reminders(), 0)          # nothing is due yet
            later = to_db(utcnow() + timedelta(hours=3))
            self.assertEqual(process_due_reminders(now=later), 2)  # both fire...
            self.assertEqual(process_due_reminders(now=later), 0)  # ...exactly once
        reminders = self.client.get(f"/api/tasks/{task['id']}/reminders",
                                    headers=self.h).get_json()["reminders"]
        self.assertTrue(all(r["delivered"] for r in reminders))

    def test_completed_tasks_do_not_notify(self):
        task = self.create_task(self.h, dueDate=soon(60), minutesBefore=30)
        self.client.post(f"/api/tasks/{task['id']}/complete", headers=self.h)
        self.assertEqual(self.fire_all(), 0)

    def test_lazy_trigger_when_listing_notifications(self):
        task = self.create_task(self.h, dueDate=soon(60), minutesBefore=30)
        self.sql("UPDATE reminders SET reminder_time = '2000-01-01T00:00:00'")   # now due
        data = self.client.get("/api/notifications", headers=self.h).get_json()
        self.assertEqual(data["unread"], 1)
        self.assertEqual(data["notifications"][0]["taskId"], task["id"])

    def test_send_reminders_cli(self):
        self.create_task(self.h, dueDate=soon(60), minutesBefore=30)
        self.sql("UPDATE reminders SET reminder_time = '2000-01-01T00:00:00'")
        result = self.app.test_cli_runner().invoke(args=["send-reminders"])
        self.assertIn("Created 1 notification", result.output)

    def test_notifications_are_private(self):
        self.create_task(self.h, dueDate=soon(60), minutesBefore=30)
        self.fire_all()
        note_id = self.client.get("/api/notifications", headers=self.h).get_json()[
            "notifications"][0]["id"]
        other = self.new_user("other@example.com")
        self.assertEqual(self.client.get("/api/notifications", headers=other).get_json()["unread"],
                         0)
        self.assertEqual(self.client.post(f"/api/notifications/{note_id}/read",
                                          headers=other).status_code, 404)


class TestPreferences(APITestCase):
    def setUp(self):
        super().setUp()
        self.h = self.new_user()

    def fire_all(self):
        with self.app.app_context():
            return process_due_reminders(now=to_db(utcnow() + timedelta(days=1)))

    def test_TC_Notify_02_preferences_apply_to_later_notifications(self):
        prefs = self.client.put("/api/preferences", headers=self.h, json={
            "notifications": {"in_app": False}, "defaultPriority": "HIGH",
            "defaultSort": "priority"}).get_json()["preferences"]
        self.assertFalse(prefs["notifications"]["in_app"])
        self.assertEqual(self.client.get("/api/preferences", headers=self.h)
                         .get_json()["preferences"]["defaultSort"], "priority")

        # In-app channel switched off -> no notification for the next reminder
        self.create_task(self.h, dueDate=soon(60), minutesBefore=30)
        self.assertEqual(self.fire_all(), 0)

        # Switched back on -> the next reminder is delivered
        self.client.put("/api/preferences", json={"notifications": {"in_app": True}},
                        headers=self.h)
        self.create_task(self.h, dueDate=soon(90), minutesBefore=30)
        self.assertEqual(self.fire_all(), 1)

    def test_task_preferences_apply_to_new_tasks_and_the_list(self):
        self.client.put("/api/preferences", json={"defaultPriority": "HIGH",
                                                  "defaultSort": "title"}, headers=self.h)
        self.assertEqual(self.create_task(self.h, title="b")["priority"], "HIGH")   # default used
        self.assertEqual(self.create_task(self.h, title="a", priority="LOW")["priority"], "LOW")
        self.assertEqual([t["title"] for t in self.list_tasks(self.h)], ["a", "b"])  # by title

    def test_defaults_before_anything_is_saved(self):
        prefs = self.client.get("/api/preferences", headers=self.h).get_json()["preferences"]
        self.assertEqual(prefs, {"notifications": {"in_app": True, "email": False},
                                 "defaultPriority": "MEDIUM", "defaultSort": "due_date"})

    def test_invalid_preferences_rejected(self):
        for body in ({"notifications": {"sms": True}}, {"notifications": {"in_app": "yes"}},
                     {"notifications": "on"}, {"defaultPriority": "URGENT"},
                     {"defaultSort": "colour"}):
            with self.subTest(body=body):
                self.assertEqual(self.client.put("/api/preferences", json=body,
                                                 headers=self.h).status_code, 400)
