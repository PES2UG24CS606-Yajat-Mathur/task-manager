"""Categories / tags - TC-Org-03 (TMA-F-022)."""

from tests.helpers import APITestCase


class TestCategories(APITestCase):
    def setUp(self):
        super().setUp()
        self.h = self.new_user()

    def categories(self, headers=None):
        resp = self.client.get("/api/categories", headers=headers or self.h)
        return resp.get_json()["categories"]

    def test_TC_Org_03_create_or_select_categories(self):
        # Create: two new categories straight from the task form (duplicates removed)
        task = self.create_task(self.h, categories=["College", "college", "SE"])
        self.assertEqual(task["categories"], ["College", "SE"])
        self.assertEqual({c["name"]: c["taskCount"] for c in self.categories()},
                         {"College": 1, "SE": 1})

        # Select: a second task reuses "SE" instead of creating another one
        self.create_task(self.h, title="Second", categories=["se"])
        self.assertEqual({c["name"]: c["taskCount"] for c in self.categories()},
                         {"College": 1, "SE": 2})

        # Create a category on its own; the same name twice is a conflict
        self.assertEqual(self.client.post("/api/categories", json={"name": "Home"},
                                          headers=self.h).status_code, 201)
        self.assertEqual(self.client.post("/api/categories", json={"name": "home"},
                                          headers=self.h).status_code, 409)

    def test_edit_replaces_categories(self):
        task = self.create_task(self.h, categories=["College"])
        edited = self.client.patch(f"/api/tasks/{task['id']}", json={"categories": ["Home"]},
                                   headers=self.h).get_json()["task"]
        self.assertEqual(edited["categories"], ["Home"])
        cleared = self.client.patch(f"/api/tasks/{task['id']}", json={"categories": []},
                                    headers=self.h).get_json()["task"]
        self.assertEqual(cleared["categories"], [])

    def test_deleting_a_category_keeps_its_tasks(self):
        task = self.create_task(self.h, categories=["Home"])
        home_id = self.categories()[0]["id"]
        self.assertEqual(self.client.delete(f"/api/categories/{home_id}",
                                            headers=self.h).status_code, 200)
        fetched = self.client.get(f"/api/tasks/{task['id']}", headers=self.h).get_json()["task"]
        self.assertEqual(fetched["categories"], [])                 # task still there, untagged

    def test_categories_are_private(self):
        other = self.new_user("other@example.com")
        self.create_task(self.h, title="x", categories=["Secret"])
        self.assertEqual(self.categories(other), [])
        secret_id = self.categories()[0]["id"]
        self.assertEqual(self.client.delete(f"/api/categories/{secret_id}", headers=other)
                         .status_code, 404)

    def test_invalid_categories_rejected(self):
        for value in ("Work", [1, 2], ["x" * 51]):
            with self.subTest(value=str(value)[:20]):
                resp = self.client.post("/api/tasks", json={"title": "t", "categories": value},
                                        headers=self.h)
                self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.list_tasks(self.h), [])               # nothing half-saved
        self.assertEqual(self.client.post("/api/categories", json={"name": " "},
                                          headers=self.h).status_code, 400)
