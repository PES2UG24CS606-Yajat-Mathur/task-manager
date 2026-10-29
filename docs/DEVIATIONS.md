# Deviations from the submitted SRS, SAD and Test Plan

Mini-Project Part-2 asks for every deviation from the submitted documents to be recorded
and explained in the final demo. Add a row whenever a PR does something differently from
what the documents describe.

| # | Document / section | What the document says | What we implemented | Why |
|---|---|---|---|---|
| D1 | SAD 3.6, 4.6 (technology) | Language, framework and database left open | Python 3.11+, Flask 3, SQLite, plain HTML/CSS/JavaScript | One small dependency, no build step, runs on every team member's laptop. The SAD left this as an implementation decision. |
| D2 | SAD Figure 2 (class diagram) | Identifiers (`userId`, `taskId`, ...) are Strings | Integer auto-increment keys | Native SQLite keys. Ownership is checked on the server, so predictable ids are not a security problem (TC-Sec-01). |
| D3 | SAD 4.3 (API design) | Four endpoints listed (login, create, update, delete task) | Those four as designed, plus register, logout, profile, view, complete / reopen and history endpoints | SAD 4.3 says paths "may be adjusted during implementation"; the extra endpoints are needed by the Sprint 1 requirements. |
| D4 | SAD Figure 2, `Status` enumeration | ACTIVE, COMPLETED, OVERDUE | Sprint 1 stores ACTIVE / COMPLETED only | OVERDUE depends on due dates (TMA-F-023), which are in Sprint 2. |
| D5 | Test Plan section 6 (tools) | Selenium, Postman, JMeter, Jira | pytest with Flask's test client for API and security tests; GitHub Issues and Projects for tracking | One toolchain that GitHub Actions runs on every pull request. |
| D6 | Test Plan section 7 (schedule) | Test execution 22-29 Sep 2026 | Tests run automatically on every push during the sprints (Oct 2026) | The course schedule placed implementation in October. |
| D7 | Sprint plan | Sprint 1 ends 23 Oct 2026 | Sprint 1 was completed after its planned end date | Backlog and repository set-up took longer than planned. |
