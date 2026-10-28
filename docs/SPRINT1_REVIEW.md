# Sprint 1 review (planned 19-23 Oct 2026)

**Goal:** a working product where a user can register, log in and out securely, and
create, edit, prioritise, complete and delete their own tasks, with every change
checked by GitHub Actions.

**Demo video:** [`videos/sprint1-demo.mp4`](videos/sprint1-demo.mp4) (about 1 minute)

## Delivered

| PR | Raised by | Backlog issues closed | Points |
|---|---|---|---|
| Project setup and GitHub Actions | Vismay Chandra Dev | (supporting work for all items) | - |
| Registration, password hashing, login | Vishnu Narayanan Ajay | #1 TMA-F-001, #2 TMA-F-002, #10 TMA-SR-002 | 11 |
| Invalid login, sessions, logout | Yajat Mathur | #3 TMA-F-003, #4 TMA-F-004, #13 TMA-SR-004 | 5 |
| Create and edit tasks, ownership | Vismay Chandra Dev | #5 TMA-F-010, #6 TMA-F-011, #11 TMA-F-014 | 9 |
| Delete, complete / reopen, authorization | Tharunyah Sudhakar | #7 TMA-F-012, #8 TMA-F-013, #12 TMA-SR-003 | 5 |
| Task priority | Vishnu Narayanan Ajay | #9 TMA-F-020 | 1 |
| Sprint 1 review and demo video | Tharunyah Sudhakar | - | - |

**Velocity: 31 story points, 13 of 13 Sprint 1 issues closed.**

## Automation (GitHub Actions)

* `ci.yml`: on every push and pull request, flake8 plus the full pytest suite on
  Python 3.11, 3.12 and 3.13; test and coverage reports are kept as build artifacts.
* `pr-checks.yml`: every PR is auto-assigned to its author, labelled by size, and fails
  until its description links a backlog issue (`Closes #N`).
* `CODEOWNERS`: every PR requests a review from the repository owner.

## Test cases covered (Test Plan IDs, all automated in `tests/`)

TC-Auth-01, TC-Auth-02, TC-Auth-03, TC-Auth-04, TC-Task-01, TC-Task-02, TC-Task-03,
TC-Task-04, TC-Sec-01, TC-Sec-02, TC-Sec-04, TC-Org-01.

## Demo video script (about 60 seconds)

| Time | Show |
|---|---|
| 0-10 s | Create an account; try a short password first and show the error message |
| 10-20 s | Log out, log in with a wrong password ("Invalid email or password"), then the right one |
| 20-35 s | Create three tasks with different priorities; edit one |
| 35-45 s | Complete a task, reopen it; delete one (confirmation dialog appears) |
| 45-52 s | Log out; refresh the page and show you are back on the login screen |
| 52-60 s | GitHub: Actions tab with green runs, the merged PRs, Sprint 1 milestone at 100% |

Record with OBS, Xbox Game Bar (Windows + G) or QuickTime; export as MP4 under 100 MB.
