# Task Manager Application

Software Engineering mini-project, Section J, Batch 12, PES University.

| SRN | Name | GitHub |
|---|---|---|
| PES2UG24CS561 | Tharunyah Sudhakar | @tharunyah |
| PES2UG24CS594 | Vishnu Narayanan Ajay | @vishnu201917-n |
| PES2UG24CS597 | Vismay Chandra Dev | @VismayCD |
| PES2UG24CS606 | Yajat Mathur | @PES2UG24CS606-Yajat-Mathur |

A web application to create, organise, prioritise, schedule and complete personal tasks,
built from our SRS v1.0, SAD v1.0 and Software Test Plan v1.0.

The backlog lives in this repository's **Issues** (one issue per SRS requirement, with
story points as `points: N` labels and the sprint as the milestone).

## Run it locally

Needs Python 3.11 or newer.

```bash
python -m venv .venv
.venv\Scripts\activate               # macOS / Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
python run.py                        # open http://127.0.0.1:5000
```

The SQLite database is created automatically at `instance/taskmanager.sqlite3`.

## Tests and checks

```bash
pytest                    # test names carry the Test Plan IDs, e.g. test_TC_Auth_01_...
flake8 .                  # style check
```

GitHub Actions runs both on every push and pull request (`.github/workflows/ci.yml`), and
`.github/workflows/pr-checks.yml` makes sure every PR is linked to a backlog issue.
How we raise and review PRs: [`CONTRIBUTING.md`](CONTRIBUTING.md).
Sprint plan: [`docs/SPRINT_PLAN.md`](docs/SPRINT_PLAN.md).
