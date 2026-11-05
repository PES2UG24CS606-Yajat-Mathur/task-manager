"""
Sprint 3: bad input must never become a server error (Test Plan 5.1, SAD 4.4).

These tests sweep EVERY route instead of checking one example, so a route added later is
checked automatically. They would have caught DEF-01 to DEF-05 (see docs/SPRINT3_REVIEW.md).
A 4xx is the right answer to bad input; any 5xx is a failure. The fuzz test is seeded, so
it sends the same requests on every run and a failure can be reproduced.
"""

import json
import random
import re

from tests.helpers import APITestCase

HUGE = 10 ** 20                 # larger than SQLite's 64-bit integer limit
SURROGATE_JSON = '"\\ud800"'    # valid JSON, but a string that cannot be encoded as UTF-8

BAD_VALUES = [None, True, False, 0, -1, 1.5, 10 ** 30, 1e308, "", " ", "x" * 3000, "\u0000", "😀",
              "' OR 1=1--", "<script>", "../../etc/passwd", "0001-01-01T00:00:00+05:30",
              "9999-12-31T23:59:59-05:30", [], [1], {}, {"a": 1}, [[]], ["x"], [None]]
FIELDS = ["title", "description", "priority", "status", "dueDate", "categories", "reminderTime",
          "minutesBefore", "name", "email", "password", "notifications", "defaultPriority",
          "defaultSort", "role", "isActive"]


class RobustnessCase(APITestCase):
    def setUp(self):
        super().setUp()
        self.headers = self.new_user("root@example.com", admin=True)
        self.task = self.create_task(self.headers, title="Base", dueDate="2030-01-01")

    def routes(self):
        """Every API route as (method, rule, name of its integer URL argument or None)."""
        for rule in self.app.url_map.iter_rules():
            if rule.rule.startswith("/api/"):
                for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
                    yield method, rule.rule, next(iter(rule.arguments), None)

    def url(self, rule, value):
        return re.sub(r"<[^>]+>", str(value), rule)

    def assert_not_server_error(self, resp, label):
        detail = resp.get_data(as_text=True)[:200]
        self.assertLess(resp.status_code, 500, f"{label} -> {resp.status_code} {detail}")


class TestEveryRoute(RobustnessCase):
    def test_TC_Val_01b_huge_id_in_any_url_is_not_found(self):
        checked = 0
        for method, rule, arg in self.routes():
            if arg:
                resp = self.client.open(self.url(rule, HUGE), method=method, headers=self.headers, json={})
                self.assertEqual(resp.status_code, 404, f"{method} {rule}")
                checked += 1
        self.assertGreaterEqual(checked, 13)     # guards against the sweep silently checking nothing

    def test_TC_Val_01c_largest_valid_id_is_an_ordinary_not_found(self):
        resp = self.client.get(f"/api/tasks/{2 ** 63 - 1}", headers=self.headers)
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.get_json()["error"]["message"], "Task not found")

    def test_TC_Val_01d_surrogate_in_any_json_body_is_refused(self):
        """In a field, in a nested value and in a key: all get the same 400, on every route."""
        bodies = ['{"title": %s, "name": %s, "email": %s, "password": %s}' % ((SURROGATE_JSON,) * 4),
                  '{"categories": [%s]}' % SURROGATE_JSON, '{"notifications": {%s: true}}' % SURROGATE_JSON]
        for method, rule, arg in self.routes():
            if method == "GET" or rule.endswith("/logout"):
                continue
            target = self.url(rule, self.task["id"] if arg else "")
            for body in bodies:
                resp = self.client.open(target, method=method, headers=self.headers, data=body,
                                        content_type="application/json")
                self.assert_not_server_error(resp, f"{method} {rule} {body}")

    def test_TC_Val_01e_deeply_nested_json_is_refused(self):
        for opener in ("[", '{"a":'):
            # 12000 levels stays under the 64 KB body limit, so the parser really sees it
            resp = self.client.post("/api/tasks", headers=self.headers, data=opener * 12000,
                                    content_type="application/json")
            self.assertEqual(resp.status_code, 400, opener)


class TestSpecificBoundaries(RobustnessCase):
    def post_task(self, **fields):
        return self.client.post("/api/tasks", json={"title": "t", **fields}, headers=self.headers)

    def assert_field_error(self, resp, field):
        self.assertEqual(resp.status_code, 400, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["error"]["details"]["field"], field)

    def test_TC_Val_01f_huge_paging_values_are_refused_or_clamped(self):
        self.assertEqual(self.client.get(f"/api/tasks?offset={HUGE}", headers=self.headers).status_code, 400)
        self.assertEqual(self.client.get(f"/api/tasks?limit={HUGE}", headers=self.headers).status_code, 200)
        largest = self.client.get(f"/api/tasks?offset={2 ** 63 - 1}", headers=self.headers)
        self.assertEqual(largest.get_json()["count"], 0)

    def test_TC_Val_01g_dates_outside_the_supported_range_are_refused(self):
        for bad in ("0001-01-01T00:00:00+05:30", "9999-12-31T23:59:59-05:30", "0001-01-01T00:00:00Z",
                    "1899-12-31", "0999-06-15T10:00:00Z"):
            with self.subTest(date=bad):
                self.assert_field_error(self.post_task(dueDate=bad), "dueDate")
                self.assert_field_error(self.post_task(reminderTime=bad), "reminderTime")

    def test_TC_Val_01h_dates_at_the_edges_of_the_range_are_accepted(self):
        for good, stored in (("1900-01-01", "1900-01-01T23:59:59Z"), ("9999-12-31", "9999-12-31T23:59:59Z")):
            with self.subTest(date=good):
                resp = self.post_task(dueDate=good)
                self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
                self.assertEqual(resp.get_json()["task"]["dueDate"], stored)

    def test_TC_Val_01i_reminder_before_the_earliest_date_is_refused_cleanly(self):
        self.assert_field_error(self.post_task(dueDate="1900-01-01", minutesBefore=10080), "reminderTime")

    def test_TC_Val_01j_infinite_or_huge_minutes_before_is_refused(self):
        target = f"/api/tasks/{self.task['id']}/reminders"
        for raw in ("1e999", "-1e999", "1e308", str(HUGE)):
            with self.subTest(minutesBefore=raw):
                resp = self.client.post(target, data='{"minutesBefore": %s}' % raw, headers=self.headers,
                                        content_type="application/json")
                self.assert_field_error(resp, "minutesBefore")

    def test_TC_Val_01k_surrogate_in_login_and_registration_is_refused(self):
        for path, body in (("/api/auth/login", '{"email": "a@b.co", "password": %s}' % SURROGATE_JSON),
                           ("/api/auth/login", '{"email": %s, "password": "x"}' % SURROGATE_JSON),
                           ("/api/auth/register", '{"name": "n", "email": "s@b.co", "password": "abc12345%s}'
                            % SURROGATE_JSON[1:])):
            with self.subTest(path=path, body=body):
                resp = self.client.post(path, data=body, content_type="application/json")
                self.assertEqual(resp.status_code, 400, resp.get_data(as_text=True))

    def test_TC_Val_01l_valid_unicode_is_still_accepted(self):
        """The surrogate check must not refuse real text: emoji arrive as a valid surrogate PAIR."""
        title = "\\ud83d\\ude00 \\u0ca8\\u0cae\\u0cb8\\u0ccd\\u0c95\\u0cbe\\u0cb0"
        resp = self.client.post("/api/tasks", data='{"title": "%s"}' % title,
                                headers=self.headers, content_type="application/json")
        self.assertEqual(resp.status_code, 201, resp.get_data(as_text=True))
        self.assertEqual(resp.get_json()["task"]["title"], "\U0001F600 ನಮಸ್ಕಾರ")


class TestSeededFuzz(RobustnessCase):
    def test_TC_Val_01m_seeded_fuzz_of_every_route_gives_no_server_error(self):
        rng = random.Random(20261105)
        routes = [r for r in self.routes() if not r[1].endswith("/logout") and "/admin/users/" not in r[1]]
        for _ in range(3000):
            method, rule, arg = rng.choice(routes)
            value = rng.choice([self.task["id"], 0, 1, 2 ** 63 - 1, 2 ** 63, HUGE]) if arg else ""
            target = self.url(rule, value)
            kwargs = {}
            if method == "GET":
                key = rng.choice(["q", "status", "priority", "category", "sort", "order", "limit", "offset",
                                  "type", "unread"])
                kwargs["query_string"] = {key: str(rng.choice(BAD_VALUES))}
            else:
                body = {field: rng.choice(BAD_VALUES) for field in rng.sample(FIELDS, rng.randint(0, 5))}
                kwargs.update(data=json.dumps(body), content_type="application/json")
            resp = self.client.open(target, method=method, headers=self.headers, **kwargs)
            self.assert_not_server_error(resp, f"{method} {target} {kwargs}")
