"""
Entry point.

Development server:
    python run.py                 # http://127.0.0.1:5000
    python run.py --host 0.0.0.0  # reachable from other devices on the LAN (phone testing)
    python run.py --no-scheduler  # without the background reminder thread

Flask CLI (uses the `app` object below):
    flask --app run init-db
    flask --app run send-reminders     # deliver due reminders once (TMA-F-040)
"""

import argparse
import os

from app import create_app
from app.notifications import start_reminder_scheduler

app = create_app()


def main():
    parser = argparse.ArgumentParser(description="Run the Task Manager development server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5000)))
    parser.add_argument("--no-scheduler", action="store_true",
                        help="do not start the background reminder thread")
    args = parser.parse_args()

    # In debug mode Flask's reloader runs this file twice (a watcher and a worker).
    # Start the reminder thread only in the worker, so reminders are not sent twice.
    use_reloader = app.debug
    is_worker = os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not use_reloader
    if not args.no_scheduler and is_worker:
        start_reminder_scheduler(app)

    app.run(host=args.host, port=args.port, use_reloader=use_reloader)


if __name__ == "__main__":
    main()
