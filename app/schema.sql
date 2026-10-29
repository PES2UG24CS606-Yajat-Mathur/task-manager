-- =====================================================================
--  Task Manager Application - database schema (SQLite)
--  Mirrors the UML class diagram (SAD Figure 2).
--  All timestamps are stored as UTC ISO-8601 text: 'YYYY-MM-DDTHH:MM:SS'
--  (fixed width, so string comparison == chronological comparison).
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------- User
CREATE TABLE IF NOT EXISTS users (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    name                  TEXT    NOT NULL,
    email                 TEXT    NOT NULL UNIQUE COLLATE NOCASE,   -- TMA-F-001 unique account
    password_hash         TEXT    NOT NULL,                         -- TMA-SR-002 never plaintext
    role                  TEXT    NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    is_active             INTEGER NOT NULL DEFAULT 1,
    default_priority      TEXT    NOT NULL DEFAULT 'MEDIUM',        -- TMA-F-041 task preference
    default_sort          TEXT    NOT NULL DEFAULT 'due_date',      -- TMA-F-041 task preference
    created_at            TEXT    NOT NULL
);

-- ------------------------------------------------------------- Session
-- Only a SHA-256 hash of the bearer token is stored (TMA-SR-004).
CREATE TABLE IF NOT EXISTS sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash   TEXT    NOT NULL UNIQUE,
    created_at   TEXT    NOT NULL,
    expires_at   TEXT    NOT NULL,
    revoked_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

-- ---------------------------------------------------------------- Task
CREATE TABLE IF NOT EXISTS tasks (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,   -- owner
    title         TEXT    NOT NULL,
    description   TEXT    NOT NULL DEFAULT '',
    priority      TEXT    NOT NULL DEFAULT 'MEDIUM'
                  CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH')),             -- <<enum>> Priority
    status        TEXT    NOT NULL DEFAULT 'ACTIVE'
                  CHECK (status IN ('ACTIVE', 'COMPLETED')),   -- OVERDUE is derived, see DEVIATIONS
    due_date      TEXT,
    completed_at  TEXT,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL
);
-- TMA-NF-001: the task list, filters and dashboard always ask for "this user's tasks",
-- usually by status or due date. These indexes let SQLite jump straight to those rows
-- instead of reading the whole table. (IF NOT EXISTS: added to existing databases too.)
CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_tasks_user_due    ON tasks(user_id, due_date);

-- ------------------------------------------------------------ Category
CREATE TABLE IF NOT EXISTS categories (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name      TEXT    NOT NULL COLLATE NOCASE,
    UNIQUE (user_id, name)
);

-- Task 0..* <-> 0..* Category  ("tagged with")
CREATE TABLE IF NOT EXISTS task_categories (
    task_id      INTEGER NOT NULL REFERENCES tasks(id)      ON DELETE CASCADE,
    category_id  INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, category_id)
);
CREATE INDEX IF NOT EXISTS idx_task_categories_category ON task_categories(category_id);

-- ------------------------------------------------------------ Reminder
CREATE TABLE IF NOT EXISTS reminders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id        INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    reminder_time  TEXT    NOT NULL,
    delivered      INTEGER NOT NULL DEFAULT 0,
    delivered_at   TEXT
);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(delivered, reminder_time);

-- --------------------------------------------------------- TaskHistory
CREATE TABLE IF NOT EXISTS task_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id      INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    change_type  TEXT    NOT NULL,          -- CREATED, UPDATED, COMPLETED, REOPENED, ...
    details      TEXT    NOT NULL DEFAULT '{}',   -- JSON of changed fields
    timestamp    TEXT    NOT NULL
);

-- ---------------------------------------------- NotificationPreference
CREATE TABLE IF NOT EXISTS notification_preferences (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    channel   TEXT    NOT NULL CHECK (channel IN ('in_app', 'email')),
    enabled   INTEGER NOT NULL DEFAULT 1,
    UNIQUE (user_id, channel)
);

-- -------------------------------------------------------- Notification
CREATE TABLE IF NOT EXISTS notifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_id      INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
    reminder_id  INTEGER REFERENCES reminders(id) ON DELETE SET NULL,
    channel      TEXT    NOT NULL,
    message      TEXT    NOT NULL,
    created_at   TEXT    NOT NULL,
    read_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, read_at);

-- ------------------------------------------------------- SecurityEvent
-- TMA-SR-005: never contains passwords or tokens.
CREATE TABLE IF NOT EXISTS security_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type  TEXT    NOT NULL,     -- LOGIN_SUCCESS, LOGIN_FAILED, LOGOUT, ACCESS_DENIED, ADMIN_*
    user_id     INTEGER,
    email       TEXT,
    ip_address  TEXT,
    details     TEXT    NOT NULL DEFAULT '{}',
    created_at  TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_security_events_type ON security_events(event_type, email, created_at);
