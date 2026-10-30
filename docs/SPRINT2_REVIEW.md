# Sprint 2 review (planned 26-30 Oct 2026)

**Goal:** organise tasks (status, categories, due dates), reminders and notifications,
search / filter / sort, a progress dashboard, administration, and every non-functional
and remaining security requirement verified by automated tests. Then freeze development
at tag `v1.0`.

**Demo video:** [`videos/sprint2-demo.mp4`](videos/sprint2-demo.mp4) (about 2 minutes)

## Delivered

| Stage | Raised by | Backlog issues closed | Points |
|---|---|---|---|
| S2-01 Due dates and categories | Vishnu Narayanan Ajay | #16 TMA-F-023, #15 TMA-F-022 | 4 |
| S2-02 Status (automatic OVERDUE) and dashboard | Yajat Mathur | #14 TMA-F-021, #21 TMA-F-033 | 4 |
| S2-03 Search, filter, sort | Tharunyah Sudhakar | #18 TMA-F-030, #19 TMA-F-031, #20 TMA-F-032 | 7 |
| S2-04 Reminders, notifications, preferences | Vismay Chandra Dev | #17 TMA-F-024, #22 TMA-F-040, #23 TMA-F-041 | 13 |
| S2-05 Security logging, data security, consistency | Tharunyah Sudhakar | #31 TMA-SR-005, #27 TMA-NF-003, #28 TMA-NF-004 | 9 |
| S2-06 Administration, HTTPS, performance | Yajat Mathur | #24 TMA-F-042, #30 TMA-SR-001, #25 TMA-NF-001 | 11 |
| S2-07 Availability, responsive and accessible UI | Vishnu Narayanan Ajay | #26 TMA-NF-002, #29 TMA-NF-005 | 8 |
| S2-08 Final documentation and demo video | Vismay Chandra Dev | (refs #1) | - |

**Velocity: 56 story points, 18 of 18 Sprint 2 issues closed.**
**Project total: 87 story points, 31 of 31 backlog issues closed, 121 automated tests.**

| Member | Sprint 1 | Sprint 2 | Total |
|---|---|---|---|
| Vishnu Narayanan Ajay | 12 | 12 | 24 |
| Tharunyah Sudhakar | 5 | 16 | 21 |
| Vismay Chandra Dev | 9 | 13 | 22 |
| Yajat Mathur | 5 | 15 | 20 |

## Test cases covered in Sprint 2 (all automated in `tests/`)

TC-Org-02, TC-Org-03, TC-Org-04, TC-Org-05, TC-Search-01..03, TC-Progress-01,
TC-Notify-01, TC-Notify-02, TC-Admin-01, TC-Perf-01, TC-Reliability-01, TC-Sec-02b,
TC-Sec-03, TC-Sec-05, TC-Integrity-01, TC-UX-01. The full mapping is in [`RTM.md`](RTM.md).

Manual part of TC-UX-01, checked in the browser:
- [ ] At 390 px wide (dev tools, *Toggle device toolbar*), nothing scrolls sideways
- [ ] Every action works with the keyboard only (Tab, Enter, Esc); the focus ring is visible
- [ ] Dark mode follows the Windows setting (*Settings, Personalisation, Colours*)

## Demo video script (about 2 minutes)

### Before recording (5 minutes)

1. `git checkout main`, `git pull`, then delete `instance\taskmanager.sqlite3` for a clean start.
2. Make the admin account: `flask --app run create-admin` (name `Admin`, email
   `admin@demo.com`, any password with a letter and a number).
3. `python run.py`, open http://127.0.0.1:5000, register yourself (for example
   `demo@demo.com`) and add three tasks:
   * "Old lab record": due **yesterday**, category `College` (it shows as Overdue)
   * "Submit SE sprint 2": priority High, due tomorrow, categories `College, SE`
   * "Buy groceries": priority Low, category `Home`, no due date
4. Start the recorder: Win + Alt + R (Xbox Game Bar) or OBS. Start recording on the app,
   not on the recorder's own window.

### Recording

| Time | Show |
|---|---|
| 0:00-0:15 | The dashboard: Active / Overdue / Completed counts, "Due in the next 7 days", category chips. Point at the red Overdue task. |
| 0:15-0:35 | **New task** "Viva prep": priority High, status Active, due date **2 minutes from now**, categories `College`, reminder **At the due time**. Save. It appears with its date stamp and "Reminder ..." line. |
| 0:35-0:55 | Type `lab` in Search. Clear it. Status filter **Overdue**. Click the `College` chip. Sort by **Priority**, then set everything back to Any. |
| 0:55-1:10 | **Complete** the overdue task: the Overdue count drops and Completed goes up. Edit a task and change its status back to Active. |
| 1:10-1:25 | **Preferences**: default priority High, default sort Priority, Save; the list re-sorts. By now the reminder has fired: the **Notifications** badge shows 1; open it. |
| 1:25-1:45 | Log out. Log in once with a wrong password ("Invalid email or password"), then log in as `admin@demo.com`. **Admin**: the user list, **Deactivate** the demo user, and the security events (LOGIN_FAILED, ADMIN_UPDATE_USER). |
| 1:45-1:55 | F12, *Toggle device toolbar*, iPhone width: the layout stacks. Optional: dark mode. |
| 1:55-2:05 | GitHub: green Actions run, all Sprint 2 PRs merged, the **Sprint 2** milestone at 100%, the `v1.0` tag (or show it after tagging). |

Trim the first and last second (the recorder window). Save as
`task-manager\docs\videos\sprint2-demo.mp4`, under 100 MB. Narrate live at the demo, or
record your voice while recording.

## Deviations found in this sprint

D8 to D14 (compressed sprint, e-mail channel stub, task preferences, login lockout,
TLS by a reverse proxy, availability measured only once deployed, no offline sync).
Full list with reasons in [`DEVIATIONS.md`](DEVIATIONS.md).

## Freezing development (end of Sprint 2)

After this PR is merged, development is frozen at tag **`v1.0`**:

```bat
git checkout main
git pull
git tag -a v1.0 -m "Task Manager v1.0 - end of Sprint 2, development frozen"
git push origin v1.0
```

(`python ..\sprint2-kit\pr.py freeze` runs exactly these commands after checking that every
stage is merged.) The tag is the version shown at the final demo. Any later change would
need a new PR and a new tag (`v1.0.1`), and none is planned.
