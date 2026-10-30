# Task Manager Application

Software Engineering mini-project, Section J, Batch 12, PES University.
**Version 1.0** (development frozen at tag `v1.0`, end of Sprint 2, 30 Oct 2026).

| SRN | Name | Role | GitHub |
|---|---|---|---|
| PES2UG24CS561 | Tharunyah Sudhakar | QA Lead | @tharunyah |
| PES2UG24CS594 | Vishnu Narayanan Ajay | Dev Lead | @vishnu201917-n |
| PES2UG24CS597 | Vismay Chandra Dev | Developer / Test Engineer | @VismayCD |
| PES2UG24CS606 | Yajat Mathur | Developer / Test Engineer, repo owner | @PES2UG24CS606-Yajat-Mathur |

A web application to create, organise, prioritise, schedule and complete personal tasks,
built from our SRS v1.0, SAD v1.0 and Software Test Plan v1.0. All 31 SRS requirements
are implemented and covered by 121 automated tests.

## Features

| Area | What you can do | Requirements |
|---|---|---|
| Accounts | Register, log in, log out; passwords hashed with scrypt; sessions expire | TMA-F-001..004, TMA-SR-002, TMA-SR-004 |
| Tasks | Create, edit, delete (with confirmation), complete and reopen | TMA-F-010..013 |
| Privacy | Nobody can see or change another user's tasks | TMA-F-014, TMA-SR-003 |
| Organising | Priority, status (Overdue is automatic), categories / tags, due dates | TMA-F-020..023 |
| Reminders | Remind me at the due time or 15 min / 1 hour / 1 day before; in-app notifications | TMA-F-024, TMA-F-040 |
| Finding | Search by keyword, filter by status / priority / category, sort five ways | TMA-F-030..032 |
| Dashboard | Active / overdue / completed counts, completion rate, due in the next 7 days | TMA-F-033 |
| Preferences | Notification channels, default priority, default sort | TMA-F-041 |
| Administration | List, (de)activate, promote and delete users; security event log | TMA-F-042, TMA-SR-005 |
| Quality | HTTPS enforcement, security headers, login lockout, p95 well under 3 s, transactional writes, health check, responsive and accessible UI with dark mode | TMA-NF-001..005, TMA-SR-001 |

## Run it locally

Needs Python 3.11 or newer. Windows (cmd):

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
python run.py
```

macOS / Linux: the same, with `source .venv/bin/activate`. Then open
http://127.0.0.1:5000. The database is created automatically at
`instance/taskmanager.sqlite3`.

Useful extras:

```bat
flask --app run create-admin      :: make an administrator (asks for name, email, password)
flask --app run send-reminders    :: deliver due reminders once (run.py also does it every 30 s)
python run.py --https             :: https://127.0.0.1:5000, self-signed (pip install cryptography)
python run.py --host 0.0.0.0      :: open it from a phone on the same Wi-Fi
```

Production setup, HTTPS, environment variables and backups:
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Tests and checks

```bat
pytest                     :: 121 tests; names carry the Test Plan IDs (TC-Auth-01, ...)
pytest -k TC_Sec           :: only the security test cases
pytest -s tests/test_performance.py    :: prints the measured dashboard p95
pytest --cov=app           :: with line coverage
flake8 .                   :: style check
```

GitHub Actions (`.github/workflows/ci.yml`) runs flake8 and the full suite on Python
3.11, 3.12 and 3.13 for every push and pull request, and keeps a JUnit report and coverage
as build artifacts. `.github/workflows/pr-checks.yml` makes sure every PR is linked to a
backlog issue. Requirement-to-code-to-test mapping: [`docs/RTM.md`](docs/RTM.md).

## Architecture

A layered monolith with one module per SAD component (SAD 3.5):

```
app/
  __init__.py        application factory, HTTPS redirect, security headers, /api/health
  auth.py            Authentication Module      /api/auth/*
  tasks.py           Task Module                /api/tasks/*
  access.py          Access Control             ownership check used by every task route
  status.py          status rules               OVERDUE derived from the due date
  scheduling.py      Scheduling Module          /api/categories, /api/tasks/<id>/reminders
  search.py          Search Module              query builder for search / filter / sort
  dashboard.py       Dashboard Module           /api/dashboard/summary
  notifications.py   Notification Module        /api/notifications, /api/preferences
  admin.py           Administration Module      /api/admin/*
  security.py        hashing, tokens, @login_required, @admin_required, security log
  validators.py      input validation           errors.py: consistent JSON errors
  db.py, schema.sql  Application Database (SQLite)
  static/            User / Admin UI (HTML, CSS, JavaScript; no build step)
tests/               one file per feature, unittest style, run with pytest
```

## API

Every endpoint except register, login and health needs `Authorization: Bearer <sessionToken>`.
Errors always look like `{"status": "error", "error": {"code": "...", "message": "..."}}`.

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register` | `{name, email, password}` create an account |
| POST | `/api/auth/login` | `{email, password}` returns `sessionToken` |
| POST | `/api/auth/logout` | end the current session |
| GET / PATCH | `/api/auth/me` | read / update my profile |
| GET | `/api/tasks?q=&status=&priority=&category=&sort=&order=` | search, filter, sort my tasks |
| POST | `/api/tasks` | `{title, description?, priority?, status?, dueDate?, categories?, minutesBefore? or reminderTime?}` |
| GET / PATCH / DELETE | `/api/tasks/<id>` | read / edit / delete one task |
| POST | `/api/tasks/<id>/complete`, `/reopen` | change completion |
| GET | `/api/tasks/<id>/history` | change log |
| GET / POST | `/api/tasks/<id>/reminders` | list / add reminders |
| DELETE | `/api/reminders/<id>` | remove a reminder |
| GET / POST | `/api/categories` | list / create categories |
| DELETE | `/api/categories/<id>` | delete a category (tasks are kept) |
| GET | `/api/dashboard/summary` | progress summary |
| GET | `/api/notifications?unread=true` | my notifications |
| POST | `/api/notifications/<id>/read`, `/read-all` | mark as read |
| GET / PUT | `/api/preferences` | notification and task preferences |
| GET | `/api/admin/users` | (admin) list users |
| PATCH / DELETE | `/api/admin/users/<id>` | (admin) `{role?, isActive?}` / delete |
| GET | `/api/admin/security-events?type=` | (admin) security log |
| GET | `/api/health` | uptime probe (no login) |

## Project process

* **Backlog:** one GitHub issue per SRS requirement (#1-#31), with story points as
  `points: N` labels, the owner as assignee and the sprint as milestone, on the repository's
  Project board.
* **Sprints:** plan in [`docs/SPRINT_PLAN.md`](docs/SPRINT_PLAN.md); reviews in
  [`docs/SPRINT1_REVIEW.md`](docs/SPRINT1_REVIEW.md) and
  [`docs/SPRINT2_REVIEW.md`](docs/SPRINT2_REVIEW.md); demo videos in
  [`docs/videos/`](docs/videos/).
* **Pull requests:** raised by the member assigned the issues, reviewed and merged by the
  repository owner, only after GitHub Actions is green. Rules in
  [`CONTRIBUTING.md`](CONTRIBUTING.md).
* **Deviations** from the SRS / SAD / Test Plan, with reasons:
  [`docs/DEVIATIONS.md`](docs/DEVIATIONS.md).
