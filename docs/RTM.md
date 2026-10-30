# Requirements Traceability Matrix: implementation status

This completes the RTM in SRS section 8 and SAD 5.4, where the status column was **N** for
every row. Each requirement is traced to its backlog issue, the pull request that
delivered it, the code, and the automated tests that prove it.

**Status:** **P** = implemented and passing its automated tests in CI, **A** = accepted at
the final demo (tick it after the demo), **N** = not started.

Tests are `file::test name` in `tests/`, as they appear in the GitHub Actions report.
121 automated tests in total.

## Functional requirements

| Req ID | Requirement | Issue | PR | Code | Automated tests | Status |
|---|---|---|---|---|---|---|
| TMA-F-001 | User registration | #1 | S1-02 | `app/auth.py` register | `test_auth::test_TC_Auth_01_register_creates_unique_account`, `test_TC_Auth_01b_register_validates_input` | P |
| TMA-F-002 | User login | #2 | S1-02 | `app/auth.py` login | `test_auth::test_TC_Auth_02_valid_login_returns_session_token`, `test_sessions::test_TC_Auth_02b_token_gives_access_to_protected_routes` | P |
| TMA-F-003 | Invalid login rejection | #3 | S1-03 | `app/auth.py` login | `test_invalid_login::test_TC_Auth_03_invalid_credentials_rejected`, `test_security_logging::test_TC_Auth_03b_repeated_failures_are_rate_limited` | P |
| TMA-F-004 | User logout | #4 | S1-03 | `app/auth.py` logout | `test_sessions::test_TC_Auth_04_logout_terminates_session` | P |
| TMA-F-010 | Create task | #5 | S1-04 | `app/tasks.py` create_task | `test_tasks::test_TC_Task_01_create_task_appears_in_list`, `test_TC_Task_01b_create_requires_title` | P |
| TMA-F-011 | Edit task | #6 | S1-04 | `app/tasks.py` update_task | `test_tasks::test_TC_Task_02_edit_task`, `test_TC_Task_02b_invalid_field_rejects_whole_update` | P |
| TMA-F-012 | Delete task with confirmation | #7 | S1-05 | `app/tasks.py` delete_task, confirm dialog in `app/static/` | `test_task_lifecycle::test_TC_Task_03_delete_task` | P |
| TMA-F-013 | Complete / reopen task | #8 | S1-05 | `app/tasks.py` complete / reopen | `test_task_lifecycle::test_TC_Task_04_complete_and_reopen` | P |
| TMA-F-014 | No access to other users' tasks | #11 | S1-04 | `app/access.py` get_owned_task | `test_access_control::test_TC_Sec_01_cannot_access_another_users_task` | P |
| TMA-F-020 | Task priority | #9 | S1-06 | `app/validators.py` clean_priority | `test_priority::test_TC_Org_01_priority_saved_and_displayed` | P |
| TMA-F-021 | Task status (OVERDUE derived) | #14 | S2-02 | `app/status.py`, `app/tasks.py` | `test_status::test_TC_Org_02_status_assigned_and_updated`, `test_overdue_is_derived_from_the_due_date` | P |
| TMA-F-022 | Categories / tags | #15 | S2-01 | `app/scheduling.py` | `test_categories::test_TC_Org_03_create_or_select_categories`, `test_categories_are_private` | P |
| TMA-F-023 | Due date | #16 | S2-01 | `app/validators.py` clean_optional_datetime, `app/tasks.py` | `test_due_dates::test_TC_Org_04_due_date_stored_and_displayed`, `test_due_date_can_be_changed_and_cleared` | P |
| TMA-F-024 | Task reminders | #17 | S2-04 | `app/scheduling.py` reminders, `app/notifications.py` | `test_reminders::test_TC_Org_05_reminder_configured_and_stored`, `test_notifications::test_TC_Org_05b_reminder_triggered_once_at_its_time` | P |
| TMA-F-030 | Search | #18 | S2-03 | `app/search.py` | `test_search::test_TC_Search_01_keyword_matches_title_or_description` | P |
| TMA-F-031 | Filter | #19 | S2-03 | `app/search.py` | `test_search::test_TC_Search_02_filters` | P |
| TMA-F-032 | Sort | #20 | S2-03 | `app/search.py` | `test_search::test_TC_Search_03_sorting` | P |
| TMA-F-033 | Progress summary (dashboard) | #21 | S2-02 | `app/dashboard.py` | `test_dashboard::test_TC_Progress_01_counts_match_task_data` | P |
| TMA-F-040 | Notifications | #22 | S2-04 | `app/notifications.py` | `test_notifications::test_TC_Notify_01_notification_generated_for_due_reminder` | P |
| TMA-F-041 | Notification and task preferences | #23 | S2-04 | `app/notifications.py` preferences | `test_notifications::test_TC_Notify_02_preferences_apply_to_later_notifications`, `test_task_preferences_apply_to_new_tasks_and_the_list` | P |
| TMA-F-042 | Admin user management | #24 | S2-06 | `app/admin.py` | `test_admin::test_TC_Admin_01_only_admins_can_manage_users`, `test_deactivation_logs_the_user_out_and_blocks_login` | P |

## Non-functional requirements

| Req ID | Requirement | Issue | PR | Code | Automated tests | Status |
|---|---|---|---|---|---|---|
| TMA-NF-001 | Dashboard within 3 s for 95% of requests | #25 | S2-06 | indexes in `app/schema.sql`, one-query dashboard | `test_performance::test_TC_Perf_01_dashboard_p95_under_3_seconds`, `test_task_queries_use_indexes` | P |
| TMA-NF-002 | 99.5% monthly availability | #26 | S2-07 | `/api/health`, `docs/DEPLOYMENT.md` | `test_health::test_TC_Reliability_01_health_endpoint`, `test_health_reports_database_failure` | P (health check and recovery). The monthly figure is measured once deployed |
| TMA-NF-003 | Protect passwords and user / task data | #27 | S2-05 | security headers in `app/__init__.py`, `app/security.py` | `test_passwords::test_TC_Sec_02_passwords_stored_only_as_hashes`, `test_data_protection::test_TC_Sec_02b_security_headers_present`, `test_search_input_cannot_inject_sql` | P |
| TMA-NF-004 | Data consistency | #28 | S2-05 | `app/db.py` transaction() | `test_integrity::test_TC_Integrity_01_repeated_crud_preserves_state`, `test_crash_while_saving_a_task_leaves_nothing_behind` | P |
| TMA-NF-005 | Responsive and accessible UI | #29 | S2-07 | `app/static/*` | `test_ux::test_TC_UX_01_responsive_and_every_control_is_labelled`, `test_text_colours_meet_wcag_aa_contrast_in_both_themes` | P |

## Security requirements

| Req ID | Requirement | Issue | PR | Code | Automated tests | Status |
|---|---|---|---|---|---|---|
| TMA-SR-001 | HTTPS / TLS | #30 | S2-06 | `FORCE_HTTPS`, HSTS, `TRUST_PROXY`, `run.py --https` | `test_https::test_TC_Sec_03_http_redirected_to_https_with_hsts` | P |
| TMA-SR-002 | Passwords stored only as hashes | #10 | S1-02 | `app/security.py` hash_password (scrypt) | `test_passwords::test_TC_Sec_02_passwords_stored_only_as_hashes`, `test_same_password_gets_different_hashes` | P |
| TMA-SR-003 | Server-side authorization | #12 | S1-05 | `@login_required`, `@admin_required`, `app/access.py` | `test_authorization::test_TC_Sec_01b_all_api_routes_require_login`, `test_admin_required_checks_role` | P |
| TMA-SR-004 | Session token protection | #13 | S1-03 | `app/security.py` create / validate / revoke session | `test_sessions::test_TC_Sec_04_expired_and_forged_tokens_rejected` | P |
| TMA-SR-005 | Security event logging | #31 | S2-05 | `app/security.py` log_security_event | `test_security_logging::test_TC_Sec_05_event_logged_without_secrets`, `test_failed_logins_logged_without_passwords`, `test_admin::test_TC_Sec_05b_admin_actions_logged` | P |

## Test Plan coverage

Every test case ID in the Software Test Plan has at least one automated test:
TC-Auth-01..04, TC-Task-01..04, TC-Org-01..05, TC-Search-01..03, TC-Progress-01,
TC-Notify-01..02, TC-Admin-01, TC-Perf-01, TC-Reliability-01, TC-Sec-01..05,
TC-Integrity-01, TC-UX-01.

Run only one group, for example: `pytest -k TC_Sec`.
