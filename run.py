"""
Entry point.

Development server:
    python run.py                 # http://127.0.0.1:5000
    python run.py --host 0.0.0.0  # reachable from other devices on the LAN (phone testing)

Flask CLI (uses the `app` object below):
    flask --app run init-db
"""

import argparse
import os

from app import create_app

app = create_app()


def main():
    parser = argparse.ArgumentParser(description="Run the Task Manager development server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 5000)))
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, use_reloader=app.debug)


if __name__ == "__main__":
    main()
