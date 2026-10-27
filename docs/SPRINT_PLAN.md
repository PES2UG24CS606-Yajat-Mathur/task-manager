# Sprint plan - Task Manager Application

Story points use the team's scale 1 / 3 / 5 / 8. Source: SRS v1.0.

## Sprint 1

19-23 Oct 2026. Accounts (register, login, logout), password hashing, sessions, authorization and task create / edit / delete / complete.

| Req ID | Requirement | Type | Priority | Points | Assignee | Test case |
|---|---|---|---|---|---|---|
| TMA-F-001 | The system shall allow a new user to register using valid required account information. | Functional | High | 3 | Vishnu Narayanan Ajay | TC-Auth-01 |
| TMA-F-002 | The system shall authenticate registered users using valid credentials. | Functional | High | 3 | Vishnu Narayanan Ajay | TC-Auth-02 |
| TMA-F-003 | The system shall reject invalid login credentials and display an appropriate error message. | Functional | High | 1 | Yajat Mathur | TC-Auth-03 |
| TMA-F-004 | The system shall allow an authenticated user to log out securely. | Functional | High | 1 | Yajat Mathur | TC-Auth-04 |
| TMA-F-010 | The system shall allow an authenticated user to create a task with a title and optional description. | Functional | High | 3 | Vismay Chandra Dev | TC-Task-01 |
| TMA-F-011 | The system shall allow users to edit existing tasks. | Functional | High | 3 | Vismay Chandra Dev | TC-Task-02 |
| TMA-F-012 | The system shall allow users to delete tasks after appropriate confirmation. | Functional | High | 1 | Tharunyah Sudhakar | TC-Task-03 |
| TMA-F-013 | The system shall allow users to mark a task as completed or reopen it. | Functional | High | 1 | Tharunyah Sudhakar | TC-Task-04 |
| TMA-F-020 | The system shall allow users to assign a priority level to a task. | Functional | High | 1 | Vishnu Narayanan Ajay | TC-Org-01 |
| TMA-SR-002 | The system shall store passwords only as secure password hashes using an approved password hashing mechanism. | Security | High | 5 | Vishnu Narayanan Ajay | TC-Sec-02 |
| TMA-F-014 | The system shall prevent users from accessing or modifying tasks belonging to another user. | Functional | High | 3 | Vismay Chandra Dev | TC-Sec-01 |
| TMA-SR-003 | The system shall enforce authorization so users can access and modify only their permitted resources. | Security | High | 3 | Tharunyah Sudhakar | TC-Sec-01 |
| TMA-SR-004 | The system shall protect session credentials/tokens against unauthorized reuse and invalidate them on logout or expiry. | Security | High | 3 | Yajat Mathur | TC-Sec-04 |

**31 points, 13 items.**

## Sprint 2

26-30 Oct 2026. Status, categories, due dates, reminders, search / filter / sort, dashboard, notifications, administration and all non-functional requirements.

| Req ID | Requirement | Type | Priority | Points | Assignee | Test case |
|---|---|---|---|---|---|---|
| TMA-F-021 | The system shall allow users to assign and update task status. | Functional | High | 1 | Yajat Mathur | TC-Org-02 |
| TMA-F-022 | The system shall allow users to create or select categories/tags for organizing tasks. | Functional | Medium | 3 | Vishnu Narayanan Ajay | TC-Org-03 |
| TMA-F-023 | The system shall allow users to set or change a task due date. | Functional | High | 1 | Vishnu Narayanan Ajay | TC-Org-04 |
| TMA-F-024 | The system shall allow users to configure reminders for tasks with a due date or selected reminder time. | Functional | Medium | 5 | Vismay Chandra Dev | TC-Org-05 |
| TMA-F-030 | The system shall allow users to search tasks by title or description keywords. | Functional | Medium | 3 | Tharunyah Sudhakar | TC-Search-01 |
| TMA-F-031 | The system shall allow users to filter tasks by status, priority and category/tag. | Functional | Medium | 3 | Tharunyah Sudhakar | TC-Search-02 |
| TMA-F-032 | The system shall allow users to sort tasks by due date, priority or status. | Functional | Medium | 1 | Tharunyah Sudhakar | TC-Search-03 |
| TMA-F-033 | The system shall provide a summary of active, completed and overdue tasks. | Functional | Medium | 3 | Yajat Mathur | TC-Progress-01 |
| TMA-F-040 | The system shall notify users about configured task reminders where notifications are enabled. | Functional | Medium | 5 | Vismay Chandra Dev | TC-Notify-01 |
| TMA-F-041 | The system shall allow users to manage notification and task preferences. | Functional | Medium | 3 | Vismay Chandra Dev | TC-Notify-02 |
| TMA-F-042 | The system shall provide authorized administrators with user/account management functions where administrator access is enabled. | Functional | Medium | 5 | Yajat Mathur | TC-Admin-01 |
| TMA-NF-001 | The system shall load the main task dashboard within 3 seconds for at least 95% of requests under normal load. | Non-functional | High | 3 | Yajat Mathur | TC-Perf-01 |
| TMA-NF-002 | The system shall provide 99.5% monthly availability excluding scheduled maintenance. | Non-functional | High | 3 | Vishnu Narayanan Ajay | TC-Reliability-01 |
| TMA-NF-003 | The system shall protect passwords and sensitive user/task data using appropriate security controls and shall not store passwords in plaintext. | Non-functional | High | 3 | Tharunyah Sudhakar | TC-Sec-02 |
| TMA-NF-004 | The system shall maintain data consistency so that confirmed task changes are not lost during normal operation. | Non-functional | High | 3 | Tharunyah Sudhakar | TC-Integrity-01 |
| TMA-NF-005 | The user interface shall be responsive and usable on supported desktop and mobile screen sizes and provide accessible labels and controls where applicable. | Non-functional | Medium | 5 | Vishnu Narayanan Ajay | TC-UX-01 |
| TMA-SR-001 | The system shall use HTTPS/TLS for network communication between supported clients and backend services. | Security | High | 3 | Yajat Mathur | TC-Sec-03 |
| TMA-SR-005 | The system shall record security-relevant events such as failed logins and administrative actions without recording passwords. | Security | High | 3 | Tharunyah Sudhakar | TC-Sec-05 |

**56 points, 18 items.**

## Points per member

| Member | Sprint 1 | Sprint 2 | Total |
|---|---|---|---|
| Vishnu Narayanan Ajay (@vishnu201917-n) | 12 | 12 | 24 |
| Tharunyah Sudhakar (@tharunyah) | 5 | 16 | 21 |
| Vismay Chandra Dev (@VismayCD) | 9 | 13 | 22 |
| Yajat Mathur (@PES2UG24CS606-Yajat-Mathur) | 5 | 15 | 20 |

**Total: 31 requirements, 87 story points.**
