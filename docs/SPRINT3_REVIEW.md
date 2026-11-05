# Sprint 3 review (2-6 Nov 2026)

**Goal:** fix the defects found by Part 3 testing and release `v1.0.1`. Sprint 3 is the optional
parallel activity in Mini-Project Part 3. No new features were added.

## Delivered

| Defect | What went wrong | Fix | Code | Points |
|---|---|---|---|---|
| DEF-01 | Very large integer in a URL or query gave HTTP 500 | One bounded `<int>` URL converter for the whole app gives the normal 404; a too-large offset gets 400 | `app/__init__.py`, `app/search.py`, `app/utils.py` | 1 |
| DEF-02 | Date at the edge of the supported range gave HTTP 500 | Overflow is caught, and dates before 1900 get 400 | `app/validators.py` | 1 |
| DEF-03 | `minutesBefore` of `1e999` gave HTTP 500 | Overflow is caught, giving 400 | `app/scheduling.py` | 1 |
| DEF-04 | Lone Unicode surrogate in text gave HTTP 500 | `get_json_body` refuses such text with 400 | `app/validators.py` | 1 |
| DEF-05 | Very deeply nested JSON gave HTTP 500 (found during this sprint) | `get_json_body` catches the parser's recursion error, giving 400 | `app/validators.py` | 1 |

**Velocity: 5 story points, 5 of 5 defects fixed.** Fill in the owner of each item when the backlog
issues are created.

## Testing done alongside

* `tests/test_input_robustness.py` is new. It sweeps every API route with very large ids, invalid text and
  deep JSON, and runs a seeded fuzz test of 3000 requests. It checks that valid text such as emoji and
  Kannada is still accepted.
* The four expected-failure tests from Part 3 now pass as ordinary regression tests.
* The new tests fail against the `v1.0` code with the same errors:
  [`testing/evidence/v1.0/new_tests_against_v1.0_code.txt`](testing/evidence/v1.0/new_tests_against_v1.0_code.txt).
* All Part 3 reports were regenerated for `v1.0.1`: see [`testing/README.md`](testing/README.md).

## Deviations found in this sprint

D17 (a sprint after the `v1.0` freeze) and D18 (dates before 1900 are refused). Full list in
[`DEVIATIONS.md`](DEVIATIONS.md).

## Left open on purpose

The four observations in section 6 of the System Validation Report are not defects against the SRS and were
outside this sprint's goal. The two partly met requirements (TMA-NF-002 and TMA-SR-001) need a deployed
environment.

## Release, after the PR is merged

```bat
git checkout main
git pull
git tag -a v1.0.1 -m "Task Manager v1.0.1 - Sprint 3 defect fixes"
git push origin v1.0.1
```
