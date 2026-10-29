# Deployment and availability (TMA-NF-002, TMA-SR-001)

The SRS asks for **99.5% monthly availability**, excluding scheduled maintenance. That
allows about 3.6 hours of downtime a month. This page lists what the application provides
for that, and how to run it in production.

## 1. Health check (what the monitor calls)

`GET /api/health` needs no login and returns

```json
{"status": "ok", "database": "ok", "time": "2026-10-30T10:00:00Z"}
```

with HTTP **200**, or HTTP **503** with `"database": "unavailable"` when the database
cannot be reached. Point an uptime monitor at this URL, for example UptimeRobot (free
plan, a check every 5 minutes). Its monthly report is the availability figure for
TC-Reliability-01.

## 2. Production server

`python run.py` is Flask's development server, for development only. In production use a
WSGI server, which handles many requests and restarts crashed workers.

Windows (cmd):

```bat
pip install waitress
set APP_ENV=production
set SECRET_KEY=<a long random value>
set FORCE_HTTPS=1
set TRUST_PROXY=1
waitress-serve --port=8000 run:app
```

Linux / macOS:

```bash
pip install gunicorn
APP_ENV=production SECRET_KEY=<random> TRUST_PROXY=1 \
  gunicorn -w 1 --threads 8 -b 0.0.0.0:8000 run:app
```

Use **one** worker process with several threads: SQLite allows one writer at a time.

Reminders: a WSGI server does not start `run.py`'s background thread, so schedule
`flask --app run send-reminders` every minute (cron, or Windows Task Scheduler).
Reminders are also delivered whenever a user's browser checks for notifications.

Run the server under something that restarts it after a crash or a reboot: a Windows
service (NSSM), systemd with `Restart=always`, Docker with `--restart unless-stopped`, or
the hosting platform's own process manager.

## 3. HTTPS (TMA-SR-001)

| Where | How |
|---|---|
| Your laptop | `python run.py --https` serves `https://127.0.0.1:5000` with a throw-away self-signed certificate (needs `pip install cryptography`; the browser warns once, click *Advanced, Continue*) |
| Production | A reverse proxy (nginx, Caddy, or the hosting platform) holds the real certificate and forwards to the app. Run the app with `FORCE_HTTPS=1` (the default when `APP_ENV=production`) and `TRUST_PROXY=1` |

With `FORCE_HTTPS` on, every plain-HTTP request is redirected to HTTPS (301), and HTTPS
responses carry `Strict-Transport-Security`, so browsers keep using HTTPS for a year.
`TRUST_PROXY` must only be set behind a proxy you control; without one, any client could
fake the `X-Forwarded-Proto: https` header.

## 4. Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `APP_ENV` | `development` | `production` turns off debug mode and turns on `FORCE_HTTPS` |
| `SECRET_KEY` | dev value | set a long random value in production |
| `DATABASE` | `instance/taskmanager.sqlite3` | path of the SQLite file |
| `SESSION_LIFETIME_HOURS` | `8` | how long a login lasts |
| `FORCE_HTTPS` | off (on in production) | redirect HTTP to HTTPS, send HSTS |
| `TRUST_PROXY` | off | trust `X-Forwarded-Proto` / `-For` from the reverse proxy |
| `MAX_FAILED_LOGINS` | `5` | failed logins per email before a lockout |
| `FAILED_LOGIN_WINDOW_MIN` | `15` | how long the lockout window is, in minutes |
| `REMINDER_POLL_SECONDS` | `30` | how often `run.py`'s reminder thread checks |
| `EMAIL_NOTIFICATIONS_ENABLED` | off | turn on the e-mail channel (stub, see `app/notifications.py`) |

Make a secret key with: `python -c "import secrets; print(secrets.token_hex())"`

## 5. Backups and recovery

The whole database is one file, so a nightly copy is enough for this project:

```bash
sqlite3 instance/taskmanager.sqlite3 ".backup backups/tm-2026-10-30.sqlite3"
```

To recover, stop the app, copy the backup over `instance/taskmanager.sqlite3`, and start
the app again. Every write goes through a transaction (TMA-NF-004), so a crash never
leaves a half-saved task in the file.
