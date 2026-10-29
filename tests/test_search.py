"""Search, filter and sort - TC-Search-01..03 (TMA-F-030, TMA-F-031, TMA-F-032)."""

from tests.helpers import APITestCase


class TestSearch(APITestCase):
    def setUp(self):
        super().setUp()
        self.h = self.new_user()
        # Five tasks covering every status, priority and category combination we test
        self.create_task(self.h, title="Prepare SRS document", priority="HIGH",
                         dueDate="2030-01-10T00:00:00Z", categories=["College"])
        self.create_task(self.h, title="Buy milk", description="and bread", priority="LOW",
                         categories=["Home"])
        self.create_task(self.h, title="Review test plan", description="STP document",
                         priority="MEDIUM", dueDate="2030-01-05T00:00:00Z", categories=["College"])
        self.create_task(self.h, title="Old assignment", priority="HIGH",
                         dueDate="2020-01-01T00:00:00Z")            # overdue
        done = self.create_task(self.h, title="Finished task", priority="LOW",
                                dueDate="2030-02-01T00:00:00Z")
        self.client.post(f"/api/tasks/{done['id']}/complete", headers=self.h)

    def titles(self, query):
        return [t["title"] for t in self.list_tasks(self.h, query)]

    def test_TC_Search_01_keyword_matches_title_or_description(self):
        self.assertEqual(set(self.titles("?q=document")),
                         {"Prepare SRS document", "Review test plan"})   # title + description
        self.assertEqual(self.titles("?q=BREAD"), ["Buy milk"])          # case-insensitive
        self.assertEqual(self.titles("?q=zzz"), [])                      # no match -> empty
        self.assertEqual(self.titles("?q=100%25"), [])                   # '%' is literal text

    def test_TC_Search_02_filters(self):
        self.assertEqual(set(self.titles("?priority=HIGH")),
                         {"Prepare SRS document", "Old assignment"})
        self.assertEqual(set(self.titles("?priority=high,low")),
                         {"Prepare SRS document", "Old assignment", "Buy milk", "Finished task"})
        self.assertEqual(self.titles("?status=OVERDUE"), ["Old assignment"])
        self.assertEqual(self.titles("?status=COMPLETED"), ["Finished task"])
        self.assertEqual(set(self.titles("?category=college")),
                         {"Prepare SRS document", "Review test plan"})
        # combined: search + filter
        self.assertEqual(self.titles("?q=document&priority=MEDIUM"), ["Review test plan"])

    def test_invalid_filters_rejected(self):
        for query in ("?status=LATE", "?priority=URGENT", "?sort=colour", "?order=up",
                      "?limit=ten"):
            with self.subTest(query=query):
                resp = self.client.get(f"/api/tasks{query}", headers=self.h)
                self.assertEqual(resp.status_code, 400)

    def test_TC_Search_03_sorting(self):
        # Default sort is by due date; tasks without one go last
        self.assertEqual(self.titles(""),
                         ["Old assignment", "Review test plan", "Prepare SRS document",
                          "Finished task", "Buy milk"])
        self.assertEqual(self.titles("?sort=due_date&order=desc")[-1], "Buy milk")
        ranks = {"HIGH": 1, "MEDIUM": 2, "LOW": 3}
        by_priority = [ranks[t["priority"]] for t in self.list_tasks(self.h, "?sort=priority")]
        self.assertEqual(by_priority, sorted(by_priority))
        by_status = [t["status"] for t in self.list_tasks(self.h, "?sort=status")]
        self.assertEqual(by_status[0], "OVERDUE")
        self.assertEqual(by_status[-1], "COMPLETED")
        self.assertEqual(self.titles("?sort=title")[0], "Buy milk")

    def test_pagination(self):
        first = self.titles("?sort=title&limit=2")
        second = self.titles("?sort=title&limit=2&offset=2")
        self.assertEqual(len(first), 2)
        self.assertFalse(set(first) & set(second))

    def test_search_never_returns_other_users_tasks(self):
        other = self.new_user("other@example.com")
        self.assertEqual(self.list_tasks(other, "?q=document"), [])
        self.assertEqual(self.list_tasks(other, "?category=College"), [])
