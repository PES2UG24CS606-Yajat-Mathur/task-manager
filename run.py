"""
Entry point.

Development server:
    python run.py                 # http://127.0.0.1:5000
    python run.py --https         # https://127.0.0.1:5000, self-signed certificate (TMA-SR-001)
    python run.py --cert c.pem --key k.pem   # HTTPS with your own certificate
    python run.py --host 0.0.0.0  # reachable from other devices on the LAN (phone testing)
    python run.py --no-scheduler  # without the background reminder thread

Flask CLI (uses the `app` object below):
    flask --app run init-db
    flask --app run send-reminders     # deliver due reminders once (TMA-F-040)
    flask --app run create-admin       # make an administrator account (TMA-F-042)
"""

import argparse
import importlib.util
import os
import sys

from app import create_app
from app.notifications import start_reminder_scheduler

app = create_app()


def main():
    parser = argparse.ArgumentParser(description="Run the Task Manager development server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5000)))
    parser.add_argument("--https", action="store_true",
                        help="serve over HTTPS with a throw-away self-signed certificate")
    parser.add_argument("--cert", help="TLS certificate file (use together with --key)")
    parser.add_argument("--key", help="TLS private key file")
    parser.add_argument("--no-scheduler", action="store_true",
                        help="do not start the background reminder thread")
    args = parser.parse_args()

    # TMA-SR-001: TLS for local testing. In production a reverse proxy (nginx, the hosting
    # platform) holds the real certificate and the app runs with FORCE_HTTPS=1, TRUST_PROXY=1.
    ssl_context = None
    if args.cert and args.key:
        ssl_context = (args.cert, args.key)
    elif args.https:
        if importlib.util.find_spec("cryptography") is None:
            sys.exit("--https needs the 'cryptography' package:  pip install cryptography")
        ssl_context = "adhoc"          # Werkzeug makes a self-signed certificate on start

    # In debug mode Flask's reloader runs this file twice (a watcher and a worker).
    # Start the reminder thread only in the worker, so reminders are not sent twice.
    use_reloader = app.debug
    is_worker = os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not use_reloader
    if not args.no_scheduler and is_worker:
        start_reminder_scheduler(app)

    app.run(host=args.host, port=args.port, ssl_context=ssl_context, use_reloader=use_reloader)


if __name__ == "__main__":
    main()
