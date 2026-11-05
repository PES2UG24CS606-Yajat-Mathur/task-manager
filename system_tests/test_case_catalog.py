"""
The master list of test cases: Test Case Document v2.0.

Each entry keeps the test case ID from the Software Test Plan / RTM. `change` records what happened
to the case during the sprints. Results are NOT written here: generate_reports.py works them out
from the real test runs (junit.xml and system_validation_results.json).

`steps` are written for a person, so that any case can also be repeated by hand in the browser.
"""

CATALOG = [
    # ------------------------------------------------------------------ Authentication
    dict(id="TC-Auth-01", req="TMA-F-001", module="Authentication", priority="High",
         title="Register a new user with valid required information",
         pre="The email address is not yet registered.",
         data="Name, unique email, password of 8-128 characters with a letter and a digit.",
         steps=["Open the app and choose Create account.", "Enter name, email and password.",
                "Submit.", "Repeat with the same email; then with a weak password and a bad email."],
         expected="A unique account is created and the user is logged in. A duplicate email gets 409 and "
                  "invalid input gets 400 with a message naming the problem.",
         change="Updated. Sprint 1 fixed the password policy (8-128 characters, a letter and a digit) and "
                "the name limit (100). Registration now also logs the user straight in."),
    dict(id="TC-Auth-02", req="TMA-F-002", module="Authentication", priority="High",
         title="Log in with valid credentials",
         pre="A registered, active account exists.", data="Registered email (any letter case) and password.",
         steps=["Open the app.", "Enter email and password.", "Submit."],
         expected="User is authenticated and reaches the task dashboard. The token works on protected routes.",
         change="Updated. Expected result now names the bearer session token chosen in Sprint 1 "
                "(SAD 4.6 left the mechanism open)."),
    dict(id="TC-Auth-03", req="TMA-F-003", module="Authentication", priority="High",
         title="Log in with invalid credentials",
         pre="A registered account exists.", data="Wrong password; unknown email; six failures in a row.",
         steps=["Log in with a wrong password.", "Log in with an unknown email.",
                "Fail five times, then try a sixth time and then the correct password."],
         expected="Rejected with 'Invalid email or password' and no session, the same message in both cases. "
                  "After 5 failures in 15 minutes login returns 429, even with the correct password.",
         change="Extended. Lockout steps added for the rate limit introduced in Sprint 2 (deviation D11)."),
    dict(id="TC-Auth-04", req="TMA-F-004", module="Authentication", priority="High",
         title="Log out", pre="User is logged in.", data="The session token in use.",
         steps=["Choose Log out.", "Call a protected page or API with the old token."],
         expected="Session ends, the login form is shown, and the old token gets 401.",
         change="Unchanged in intent; written out in full (the ID only appeared in the RTM)."),
    # ------------------------------------------------------------------ Tasks
    dict(id="TC-Task-01", req="TMA-F-010", module="Task", priority="High",
         title="Create a task with a title and optional description",
         pre="User is logged in.", data="Title up to 200 characters; description up to 2000.",
         steps=["Choose New task.", "Save with an empty title.", "Enter a title and description.", "Save."],
         expected="The empty title is refused with a clear message. The valid task is saved and appears in the list.",
         change="Updated. Length limits added. The form also sets priority, status, due date, categories and a "
                "reminder in the same step, in one transaction."),
    dict(id="TC-Task-02", req="TMA-F-011", module="Task", priority="High",
         title="Edit an existing task", pre="User owns a task.", data="New title and description; one invalid field.",
         steps=["Choose Edit on a task.", "Change the fields.", "Save.", "Send an update with one invalid field."],
         expected="Updated information is saved and displayed. An invalid or unknown field rejects the whole "
                  "update. A save with no real change writes no history.",
         change="Extended. All-or-nothing validation and the change log (TaskHistory) were added during Sprint 1."),
    dict(id="TC-Task-03", req="TMA-F-012", module="Task", priority="High",
         title="Delete a task after confirmation", pre="User owns a task.", data="An existing task.",
         steps=["Choose Delete.", "Choose Keep task.", "Choose Delete again, then Delete task."],
         expected="Keep task leaves it in place. Confirming removes it from active views and the database, "
                  "with its reminders and history.",
         change="Extended. Cancel path and cascade removal now checked."),
    dict(id="TC-Task-04", req="TMA-F-013", module="Task", priority="High",
         title="Mark a task complete and reopen it", pre="User owns an active task.", data="An active task.",
         steps=["Choose Complete.", "Choose Reopen."],
         expected="Status moves between active and completed in the list. Completing twice is harmless.",
         change="Unchanged in intent; written out in full."),
    # ------------------------------------------------------------------ Security
    dict(id="TC-Sec-01", req="TMA-F-014, TMA-SR-003", module="Access Control", priority="High",
         title="Attempt to access another user's task", pre="Two user accounts; user A owns a task.",
         data="User B's token; user A's task id; HTML in a task title.",
         steps=["As B, read, edit, delete, complete and add a reminder to A's task, and read its history.",
                "Call each protected API route with no token.", "As a normal user, call an admin route."],
         expected="Access denied (403 / 401), the task is unchanged, ACCESS_DENIED is logged, and B's list stays empty.",
         change="Extended. Now covers every route, and the log entry added in Sprint 2."),
    dict(id="TC-Sec-02", req="TMA-SR-002, TMA-NF-003", module="Authentication / Security", priority="High",
         title="Inspect stored password data and data protection", pre="Accounts exist.",
         data="Two users with one password; SQL injection strings.",
         steps=["Inspect the users table and the raw database files.", "Search for the password and token.",
                "Check response headers.", "Send SQL injection strings to login, search, filters and sort."],
         expected="Only salted scrypt hashes, different for each user. No plaintext password or raw token. "
                  "Security headers present. Injection strings have no effect.",
         change="Extended. Sprint 2 added security headers and SQL injection checks. Scrypt recorded as the approved mechanism."),
    dict(id="TC-Sec-03", req="TMA-SR-001", module="Network Security", priority="High",
         title="HTTPS / TLS for network communication", pre="Server started with FORCE_HTTPS on.",
         data="A plain-HTTP request; an HTTPS request.",
         steps=["Send a plain-HTTP request.", "Start with run.py --https and connect over TLS.",
                "Read the protocol version and the HSTS header."],
         expected="HTTP gets 301 to https://. TLS 1.2 or later is negotiated. HSTS is sent.",
         change="Changed. A trusted certificate belongs to the hosting environment, so this case verifies "
                "enforcement and a self-signed TLS connection (deviation D12)."),
    dict(id="TC-Sec-04", req="TMA-SR-004", module="Session Management", priority="High",
         title="Session tokens are protected and invalidated", pre="User is logged in.",
         data="Forged, missing, logged-out and expired tokens.",
         steps=["Call a protected route with each kind of token.", "Check the sessions table."],
         expected="All are refused with 401. The database holds only a SHA-256 hash of each token.",
         change="Unchanged in intent; written out in full."),
    dict(id="TC-Sec-05", req="TMA-SR-005", module="Security / Audit", priority="High",
         title="Security events are logged without secrets", pre="Administrator account exists.",
         data="Failed logins with a recognisable password.",
         steps=["Fail a login, log in, log out, trigger an access denial and an admin action.",
                "Read security_events and the application log."],
         expected="The events are recorded with type, email and IP. No password or token appears in either place.",
         change="Unchanged in intent; written out in full. Administrators can also read events through the API."),
    dict(id="TC-Val-01", req="Test Plan 5.1, SAD 4.4", module="Input validation", priority="Medium",
         title="Basic input validation and fuzz style checks", pre="User is logged in.",
         data="Broken JSON, wrong types, over-long text, impossible dates, boundary values.",
         steps=["Send each malformed request.", "Check the status and the error format.",
                "Check the application still works."],
         expected="Every malformed request gets a 4xx in the standard error format, never a 500. The application stays healthy.",
         change="NEW in Part 3. Test Plan 5.1 asks for these checks but no test case ID was assigned to them. "
                "Failed at v1.0 (DEF-01 to DEF-04). Sprint 3 fixed the defects and extended the case to sweep "
                "every route with a seeded fuzz test, which also found DEF-05."),
    # ------------------------------------------------------------------ Organisation
    dict(id="TC-Org-01", req="TMA-F-020", module="Task / Scheduling", priority="High",
         title="Assign a priority to a task", pre="User is logged in.", data="LOW, MEDIUM, HIGH; an invalid value.",
         steps=["Create a task with High priority.", "Change the priority.", "Send an invalid value."],
         expected="Selected priority is saved and displayed. An invalid value gets 400. The change is in the history.",
         change="Unchanged in intent; written out in full."),
    dict(id="TC-Org-02", req="TMA-F-021", module="Task / Scheduling", priority="High",
         title="Assign and update task status", pre="User owns a task.", data="ACTIVE, COMPLETED; a past due date.",
         steps=["Set the status to Completed and back.", "Give an active task a past due date.",
                "Try to set OVERDUE by hand."],
         expected="Status is saved and shown. A past-due active task reads Overdue automatically. Setting OVERDUE by hand gets 400.",
         change="Changed. OVERDUE is derived from the due date rather than stored or chosen (deviation D4)."),
    dict(id="TC-Org-03", req="TMA-F-022", module="Task / Scheduling", priority="Medium",
         title="Create or select categories / tags", pre="User is logged in.", data="New names; an existing name in another letter case.",
         steps=["Save a task with new category names.", "Save another using an existing name in lower case.",
                "Delete a category."],
         expected="Task is linked to the categories. Names are reused regardless of case. Deleting a category keeps its tasks.",
         change="Extended. Case-insensitive reuse and per-user privacy added in Sprint 2."),
    dict(id="TC-Org-04", req="TMA-F-023", module="Scheduling", priority="High",
         title="Set or change a task due date", pre="User owns a task.", data="Local date and time; invalid dates; empty value.",
         steps=["Enter a due date in local time.", "Change it.", "Clear it.", "Send an invalid date."],
         expected="The date is stored as UTC and displayed correctly in local time. It can be cleared. Invalid dates get 400.",
         change="Extended. The UTC storage and local display convention was fixed in Sprint 2."),
    dict(id="TC-Org-05", req="TMA-F-024", module="Notification", priority="Medium",
         title="Configure a reminder", pre="User owns a task with a due date.", data="At the due time; 15, 60 or 1440 minutes before; an exact time.",
         steps=["Choose a reminder in the task form.", "Check it is shown on the task.", "Wait until it is due."],
         expected="Reminder is stored and fires once at the selected time. A time in the past or a relative "
                  "reminder without a due date gets 400.",
         change="Updated. The relative reminder options were defined in Sprint 2."),
    # ------------------------------------------------------------------ Search and progress
    dict(id="TC-Search-01", req="TMA-F-030", module="Search", priority="Medium",
         title="Search tasks by title or description keyword", pre="User has several tasks.", data="Matching and non-matching keywords.",
         steps=["Type a keyword from a description.", "Type a word that matches nothing."],
         expected="Matching tasks are returned and non-matching tasks are excluded. Other users' tasks are never returned.",
         change="Unchanged from the Test Plan sample."),
    dict(id="TC-Search-02", req="TMA-F-031", module="Search", priority="Medium",
         title="Filter by status, priority and category", pre="User has varied tasks.", data="Each filter value; an invalid value.",
         steps=["Apply each filter in turn.", "Clear the filters.", "Send an invalid filter value."],
         expected="Only matching tasks are displayed. An invalid value gets 400.",
         change="Updated. Overdue added as a filter value (follows D4)."),
    dict(id="TC-Search-03", req="TMA-F-032", module="Search", priority="Medium",
         title="Sort by due date, priority or status", pre="User has varied tasks.", data="Each sort field; both orders.",
         steps=["Choose each sort option.", "Reverse the order."],
         expected="The selected order is applied. Tasks without a due date come last.",
         change="Extended. Sorting by creation date and title, and paging, added in Sprint 2."),
    dict(id="TC-Progress-01", req="TMA-F-033", module="Dashboard", priority="Medium",
         title="Progress summary", pre="User has active, completed and overdue tasks.", data="A mix of task states.",
         steps=["Open the dashboard.", "Compare its counts with the task data.", "Complete a task and check again."],
         expected="Counts match the underlying task data. Other users' tasks are not counted.",
         change="Extended. Completion rate and 'due in the next 7 days' added in Sprint 2."),
    # ------------------------------------------------------------------ Notifications and admin
    dict(id="TC-Notify-01", req="TMA-F-040", module="Notification", priority="Medium",
         title="Notification generated for a due reminder", pre="A reminder is about to fall due.", data="A reminder a few seconds away.",
         steps=["Wait for the reminder without using the app.", "Open the app and read the badge and list.", "Mark all as read."],
         expected="Exactly one in-app notification is created by the background thread. The badge shows it. "
                  "A completed task gives no notification.",
         change="Changed. In-app delivery is fully tested. The e-mail provider is a stub tested at its interface (deviation D9)."),
    dict(id="TC-Notify-02", req="TMA-F-041", module="Notification", priority="Medium",
         title="Manage notification and task preferences", pre="User is logged in.", data="In-app off; default priority and sort.",
         steps=["Open Preferences and change the values.", "Save.", "Create a task.", "Let a reminder fire."],
         expected="Changes are saved and applied: the new defaults are used and no in-app notification is created while it is off.",
         change="Extended. Task preferences added, which the SAD class diagram did not model (deviation D10)."),
    dict(id="TC-Admin-01", req="TMA-F-042", module="Administration", priority="Medium",
         title="Administrator user management", pre="An administrator made with flask create-admin.", data="Admin, normal and anonymous users.",
         steps=["As a normal user and anonymously, call an admin route.", "As admin, deactivate a user.",
                "Try to use that user's session and to log in."],
         expected="Only administrators reach admin functions. A deactivated user is logged out at once and cannot log in. "
                  "Admins cannot lock themselves out.",
         change="Extended. Self-lockout rule and command-line creation of the first administrator added in Sprint 2."),
    # ------------------------------------------------------------------ Non-functional
    dict(id="TC-Perf-01", req="TMA-NF-001", module="Application / UI", priority="High",
         title="Load the dashboard under normal load", pre="A running server with seeded task data.",
         data="10 concurrent clients, 500 tasks per user (assumed, as the SRS does not define normal load).",
         steps=["Send the requests.", "Compute the 95th percentile.", "Repeat for search and filter."],
         expected="95th percentile response time is 3 seconds or less, with no failed requests.",
         change="Changed. A scripted load test replaces JMeter (deviation D5). Part 3 adds a run over real HTTP."),
    dict(id="TC-Reliability-01", req="TMA-NF-002", module="Infrastructure / Ops", priority="High",
         title="System availability", pre="A running server.", data="Health endpoint; abrupt kill and restart.",
         steps=["Call /api/health.", "Kill the server.", "Restart it and check again."],
         expected="Health reports status (503 when the database fails) and the service recovers. Monthly uptime of at least 99.5%.",
         change="Changed. The monthly figure can only be measured on a deployed system (deviation D13)."),
    dict(id="TC-Integrity-01", req="TMA-NF-004", module="Database / Task", priority="High",
         title="Data consistency across operations", pre="A running server.", data="Repeated create, update, complete and delete; 200 concurrent creates; a kill.",
         steps=["Repeat the operations and compare with the expected state.", "Force a failure inside a save.",
                "Create tasks concurrently.", "Kill the server and restart it."],
         expected="Database state is as expected. A failed save leaves nothing behind. Confirmed changes survive a crash.",
         change="Extended. Part 3 adds the concurrent-writer and kill recovery scenarios from SRS section 6."),
    dict(id="TC-UX-01", req="TMA-NF-005", module="UI", priority="Medium",
         title="Responsive and accessible user interface", pre="A running server; a browser.", data="360, 390, 768 and 1280 px widths; dark mode; keyboard only.",
         steps=["Check each width for sideways scroll.", "Use the main flow with the keyboard.",
                "Check accessible names and contrast.", "Switch to dark mode.", "Go offline and try to save."],
         expected="No sideways scroll or clipped controls. Keyboard flow works with a visible focus. Controls are named. "
                  "Contrast meets WCAG AA. Network failures give a clear message.",
         change="Extended. The manual Sprint 2 checklist is now automated in a real browser in Part 3."),
]

# Test functions whose names carry no TC id are attached to a case by file (and class where needed).
FILE_TO_TC = {
    "test_access_control": "TC-Sec-01", "test_admin": "TC-Admin-01", "test_app": "General",
    "test_auth": "TC-Auth-01", "test_authorization": "TC-Sec-01", "test_categories": "TC-Org-03",
    "test_dashboard": "TC-Progress-01", "test_data_protection": "TC-Sec-02", "test_due_dates": "TC-Org-04",
    "test_health": "TC-Reliability-01", "test_https": "TC-Sec-03", "test_integrity": "TC-Integrity-01",
    "test_invalid_login": "TC-Auth-03", "test_notifications": "TC-Notify-01", "test_passwords": "TC-Sec-02",
    "test_performance": "TC-Perf-01", "test_priority": "TC-Org-01", "test_reminders": "TC-Org-05",
    "test_search": "TC-Search-01", "test_security_logging": "TC-Sec-05", "test_sessions": "TC-Sec-04",
    "test_status": "TC-Org-02", "test_task_lifecycle": "TC-Task-04", "test_tasks": "TC-Task-01",
    "test_ux": "TC-UX-01", "test_part3_additions": "General", "test_input_robustness": "TC-Val-01",
}
NAME_TO_TC = {
    "test_login_email_is_case_insensitive": "TC-Auth-02", "test_login_requires_both_fields": "TC-Auth-03",
    "test_lockout_ends_when_the_window_passes": "TC-Auth-03", "test_deactivated_account_cannot_log_in": "TC-Admin-01",
    "test_delete_missing_task_returns_404": "TC-Task-03", "test_unknown_fields_rejected": "TC-Task-02",
    "test_missing_task_returns_404": "TC-Task-02", "test_task_routes_require_login": "TC-Sec-01",
    "test_invalid_filters_rejected": "TC-Search-02", "test_pagination": "TC-Search-03",
    "test_search_never_returns_other_users_tasks": "TC-Sec-01", "test_update_profile": "TC-Auth-02",
    "test_defaults_before_anything_is_saved": "TC-Notify-02", "test_invalid_preferences_rejected": "TC-Notify-02",
    "test_task_preferences_apply_to_new_tasks_and_the_list": "TC-Notify-02",
    "test_html_in_task_text_is_stored_as_plain_text": "TC-Sec-01",
    "test_deactivated_account_token_rejected": "TC-Sec-04",
    "test_DEF_01_huge_integer_in_url_or_query_is_not_a_server_error": "TC-Val-01",
    "test_DEF_02_date_outside_the_supported_range_is_not_a_server_error": "TC-Val-01",
    "test_DEF_03_infinite_minutes_before_is_not_a_server_error": "TC-Val-01",
    "test_DEF_04_lone_surrogate_in_text_is_not_a_server_error": "TC-Val-01",
    "test_register_rejects_non_json_body": "TC-Val-01",
}
# Which SAD component each test file exercises (for the Unit Test Report).
FILE_TO_MODULE = {
    "test_auth": "Authentication", "test_invalid_login": "Authentication", "test_sessions": "Authentication",
    "test_passwords": "Authentication", "test_tasks": "Task", "test_task_lifecycle": "Task",
    "test_access_control": "Access Control", "test_authorization": "Access Control", "test_priority": "Scheduling",
    "test_status": "Scheduling", "test_categories": "Scheduling", "test_due_dates": "Scheduling",
    "test_reminders": "Scheduling", "test_search": "Search", "test_dashboard": "Dashboard",
    "test_notifications": "Notification", "test_admin": "Administration", "test_security_logging": "Security",
    "test_data_protection": "Security", "test_https": "Security", "test_integrity": "Database",
    "test_performance": "Performance", "test_health": "Reliability", "test_ux": "User Interface",
    "test_app": "Application skeleton", "test_part3_additions": "Part 3 additions",
    "test_input_robustness": "Input validation (Sprint 3)",
}

# All found while testing v1.0 and fixed in Sprint 3 (v1.0.1). Test names are in tests/.
DEFECTS = [
    dict(id="DEF-01", severity="Low", cases="SV-36a, SV-36b, SV-36i", status="Fixed in v1.0.1",
         title="Very large integer in a URL or query gave HTTP 500",
         cause="Values above SQLite's 64-bit limit raised OverflowError when bound to a query. Affected every "
               "route with an id in its URL, and the offset parameter.",
         fix="One bounded <int> URL converter for the whole app, so such ids give the normal 404. "
             "An offset that is too large gets 400."),
    dict(id="DEF-02", severity="Low", cases="SV-36d, SV-36e, SV-36j", status="Fixed in v1.0.1",
         title="Date at the edge of the supported range gave HTTP 500",
         cause="Converting a year 1 or year 9999 date to UTC raised OverflowError, which was not caught. Years "
               "below 1000 were also stored in a form that could not be read back.",
         fix="clean_optional_datetime catches OverflowError and refuses dates before 1900 with the normal 400."),
    dict(id="DEF-03", severity="Low", cases="SV-36c", status="Fixed in v1.0.1",
         title="minutesBefore of 1e999 (infinity) gave HTTP 500",
         cause="int(float('inf')) raised OverflowError, which resolve_reminder_time did not catch.",
         fix="OverflowError added to the except clause, giving the normal 400."),
    dict(id="DEF-04", severity="Low", cases="SV-36f, SV-36g", status="Fixed in v1.0.1",
         title="Lone Unicode surrogate in text gave HTTP 500",
         cause="JSON such as \"\\ud800\" decodes to text that cannot be encoded as UTF-8, so SQLite or the password "
               "hash raised UnicodeEncodeError.",
         fix="get_json_body, which every route uses, refuses such text with 400. Emoji and other valid text "
             "are still accepted (SV-36l)."),
    dict(id="DEF-05", severity="Low", cases="SV-36k", status="Fixed in v1.0.1",
         title="Very deeply nested JSON gave HTTP 500",
         cause="Found in Sprint 3 by the new route-wide tests. 12000 levels of nesting exhausted the JSON parser "
               "(RecursionError), which get_json(silent=True) does not catch.",
         fix="get_json_body catches RecursionError and returns 400."),
]

OBSERVATIONS = [
    ("Debugger reachable when following the README's phone-testing tip",
     "Plain `python run.py` starts in development mode with the Werkzeug debugger on (verified: /console answers, "
     "protected by a PIN). The README suggests `python run.py --host 0.0.0.0` for phone testing, which exposes it to "
     "the local network. Suggest documenting APP_ENV=production for that command. Production mode is not affected."),
    ("A successful login does not clear earlier failed attempts",
     "Verified: 4 failures, a success, then 1 more failure locks the account for 15 minutes. Also, anyone who knows an "
     "email address can lock that account out (a known trade-off of per-email limits; D11)."),
    ("minutesBefore accepts true and 1.5",
     "Verified: both return 201 and are converted to 1. The error text says it must be a whole number. Harmless, since "
     "the UI only sends fixed values."),
    ("The 'By email' preference has no effect in v1.0",
     "E-mail is an interface-level stub, off by default (D9), yet the checkbox is offered to users without saying so."),
]
