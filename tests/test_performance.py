"""Performance - TC-Perf-01 (TMA-NF-001): dashboard within 3 seconds for 95% of requests."""

import random
import statistics
import time

from tests.helpers import APITestCase

BUDGET_SECONDS = 3.0


class TestPerformance(APITestCase):
    def seed_tasks(self, count=300):
        """Insert `count` tasks straight into the database to simulate a heavy user."""
        user_id = self.sql("SELECT id FROM users")[0]["id"]
        rng = random.Random(42)
        rows = [(user_id, f"Task {i}", rng.choice(["LOW", "MEDIUM", "HIGH"]),
                 rng.choice(["ACTIVE", "COMPLETED"]),
                 f"2026-{rng.randint(9, 12):02d}-{rng.randint(1, 28):02d}T12:00:00")
                for i in range(count)]
        for row in rows:
            self.sql("""INSERT INTO tasks (user_id, title, priority, status, due_date,
                                           created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, '2026-10-01T00:00:00', '2026-10-01T00:00:00')""",
                     row)

    def test_TC_Perf_01_dashboard_p95_under_3_seconds(self):
        h = self.new_user()
        self.seed_tasks(300)
        timings = []
        for _ in range(100):
            start = time.perf_counter()
            resp = self.client.get("/api/dashboard/summary", headers=h)
            timings.append(time.perf_counter() - start)
            self.assertEqual(resp.status_code, 200)
        # quantiles(n=100) gives the 1st..99th percentiles; index 94 is the 95th
        p95 = statistics.quantiles(timings, n=100)[94]
        print(f"\n  TC-Perf-01: dashboard p95 = {p95 * 1000:.1f} ms over 100 requests")
        self.assertLessEqual(p95, BUDGET_SECONDS)

    def test_task_list_with_300_tasks_is_fast(self):
        h = self.new_user()
        self.seed_tasks(300)
        start = time.perf_counter()
        self.assertEqual(len(self.list_tasks(h, "?limit=500&sort=priority")), 300)
        self.assertLess(time.perf_counter() - start, BUDGET_SECONDS)

    def test_task_queries_use_indexes(self):
        names = {r["name"] for r in self.sql("SELECT name FROM sqlite_master WHERE type='index'")}
        self.assertTrue({"idx_tasks_user_status", "idx_tasks_user_due"} <= names)
        # EXPLAIN QUERY PLAN shows how SQLite will run a query: it must use our index
        plan = " ".join(r["detail"] for r in self.sql(
            "EXPLAIN QUERY PLAN SELECT * FROM tasks WHERE user_id = 1 AND status = 'ACTIVE'"))
        self.assertIn("idx_tasks_user", plan)
