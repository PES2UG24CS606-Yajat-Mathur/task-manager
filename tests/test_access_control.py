"""Task ownership - TC-Sec-01 (TMA-F-014)."""

from tests.helpers import APITestCase


class TestAccessControl(APITestCase):
    def setUp(self):
        super().setUp()
        self.owner = self.new_user("owner@example.com")
        self.intruder = self.new_user("intruder@example.com")
        self.task = self.create_task(self.owner, title="Private plans")

    def intrusion_attempts(self, tid):
        """Every task operation another user might try. Later PRs add their endpoints here."""
        return [
            self.client.get(f"/api/tasks/{tid}", headers=self.intruder),
            self.client.patch(f"/api/tasks/{tid}", json={"title": "Hacked"}, headers=self.intruder),
        ]

    def test_TC_Sec_01_cannot_access_another_users_task(self):
        tid = self.task["id"]
        for resp in self.intrusion_attempts(tid):
            self.assertEqual(resp.status_code, 403)
            self.assertNotIn("Private plans", resp.get_data(as_text=True))  # no data leaked

        self.assertEqual(self.list_tasks(self.intruder), [])                # not in their list
        owner_view = self.client.get(f"/api/tasks/{tid}", headers=self.owner).get_json()["task"]
        self.assertEqual(owner_view["title"], "Private plans")              # unchanged
