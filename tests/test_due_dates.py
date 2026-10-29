"""Task due dates - TC-Org-04 (TMA-F-023)."""

from tests.helpers import APITestCase


class TestDueDates(APITestCase):
    def setUp(self):
        super().setUp()
        self.h = self.new_user()

    def patch(self, task_id, body):
        return self.client.patch(f"/api/tasks/{task_id}", json=body, headers=self.h)

    def test_TC_Org_04_due_date_stored_and_displayed(self):
        task = self.create_task(self.h, dueDate="2030-05-17T10:30:00Z")
        self.assertEqual(task["dueDate"], "2030-05-17T10:30:00Z")
        listed = {t["id"]: t["dueDate"] for t in self.list_tasks(self.h)}
        self.assertEqual(listed[task["id"]], "2030-05-17T10:30:00Z")      # shown in the list

    def test_due_date_can_be_changed_and_cleared(self):
        task = self.create_task(self.h, dueDate="2030-05-17T10:30:00Z")
        # Offsets are converted to UTC (IST +05:30 -> 05:00 UTC)
        moved = self.patch(task["id"], {"dueDate": "2030-05-18T10:30:00+05:30"}).get_json()
        self.assertEqual(moved["task"]["dueDate"], "2030-05-18T05:00:00Z")
        # A date without a time means the end of that day
        whole_day = self.patch(task["id"], {"dueDate": "2030-06-01"}).get_json()
        self.assertEqual(whole_day["task"]["dueDate"], "2030-06-01T23:59:59Z")
        # null removes the due date
        self.assertIsNone(self.patch(task["id"], {"dueDate": None}).get_json()["task"]["dueDate"])

    def test_invalid_due_date_rejected(self):
        task = self.create_task(self.h, dueDate="2030-05-17T10:30:00Z")
        for bad in ("next friday", "2030-13-40", 20301010):
            with self.subTest(bad=bad):
                resp = self.patch(task["id"], {"dueDate": bad})
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(resp.get_json()["error"]["details"]["field"], "dueDate")
        # ...and the stored value is untouched
        fetched = self.client.get(f"/api/tasks/{task['id']}", headers=self.h).get_json()["task"]
        self.assertEqual(fetched["dueDate"], "2030-05-17T10:30:00Z")

    def test_due_date_change_is_recorded_in_history(self):
        task = self.create_task(self.h)
        self.patch(task["id"], {"dueDate": "2030-01-01T09:00:00Z"})
        history = self.client.get(f"/api/tasks/{task['id']}/history",
                                  headers=self.h).get_json()["history"]
        self.assertEqual(history[-1]["details"], {"due_date": "2030-01-01T09:00:00"})
