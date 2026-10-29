"""Task reminders - TC-Org-05 (TMA-F-024). Delivery is tested in test_notifications.py."""

from datetime import timedelta

from app.utils import to_db, utcnow
from tests.helpers import APITestCase


def iso_in(**delta) -> str:
    """UTC ISO string `delta` from now, e.g. iso_in(hours=2)."""
    return to_db(utcnow() + timedelta(**delta)) + "Z"


class TestReminders(APITestCase):
    def setUp(self):
        super().setUp()
        self.h = self.new_user()

    def reminders(self, task_id):
        return self.client.get(f"/api/tasks/{task_id}/reminders",
                               headers=self.h).get_json()["reminders"]

    def test_TC_Org_05_reminder_configured_and_stored(self):
        # A reminder set together with the task: 30 minutes before the due date
        task = self.create_task(self.h, title="Viva", dueDate=iso_in(hours=2), minutesBefore=30)
        self.assertIsNotNone(task["nextReminder"])
        # A second reminder at an exact time
        extra = self.client.post(f"/api/tasks/{task['id']}/reminders",
                                 json={"reminderTime": iso_in(minutes=10)}, headers=self.h)
        self.assertEqual(extra.status_code, 201)
        stored = self.reminders(task["id"])
        self.assertEqual(len(stored), 2)
        self.assertFalse(any(r["delivered"] for r in stored))
        # The task shows the EARLIEST reminder that has not been sent yet
        fetched = self.client.get(f"/api/tasks/{task['id']}", headers=self.h).get_json()["task"]
        self.assertEqual(fetched["nextReminder"], extra.get_json()["reminder"]["reminderTime"])

    def test_minutes_before_uses_the_due_date(self):
        task = self.create_task(self.h, dueDate="2030-01-01T10:00:00Z", minutesBefore=60)
        self.assertEqual(task["nextReminder"], "2030-01-01T09:00:00Z")

    def test_invalid_reminders_rejected(self):
        task = self.create_task(self.h, dueDate=iso_in(days=1))
        bad = [{"reminderTime": iso_in(minutes=-5)},      # already in the past
               {"reminderTime": "tomorrow"},
               {"minutesBefore": "soon"}, {"minutesBefore": -1}, {"minutesBefore": 99999},
               {}]                                        # nothing given
        for body in bad:
            with self.subTest(body=body):
                self.assertEqual(self.client.post(f"/api/tasks/{task['id']}/reminders", json=body,
                                                  headers=self.h).status_code, 400)
        self.assertEqual(self.reminders(task["id"]), [])

    def test_minutes_before_needs_a_due_date(self):
        resp = self.client.post("/api/tasks", json={"title": "x", "minutesBefore": 10},
                                headers=self.h)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.list_tasks(self.h), [])     # the task was not created either

    def test_delete_reminder(self):
        task = self.create_task(self.h, dueDate=iso_in(days=1), minutesBefore=15)
        rid = self.reminders(task["id"])[0]["id"]
        self.assertEqual(self.client.delete(f"/api/reminders/{rid}", headers=self.h).status_code,
                         200)
        self.assertEqual(self.reminders(task["id"]), [])
        self.assertEqual(self.client.delete(f"/api/reminders/{rid}", headers=self.h).status_code,
                         404)

    def test_reminders_deleted_with_their_task(self):
        task = self.create_task(self.h, dueDate=iso_in(days=1), minutesBefore=15)
        self.client.delete(f"/api/tasks/{task['id']}", headers=self.h)
        self.assertEqual(self.sql("SELECT * FROM reminders"), [])     # cascade, no orphans
