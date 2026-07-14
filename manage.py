#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import subprocess


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "caufa_portal.settings")

    if len(sys.argv) > 1 and sys.argv[1] == "runserver":
        port = "8000"
        host = "127.0.0.1"
        if len(sys.argv) > 2:
            addrport = sys.argv[2]
            if ":" in addrport:
                host, port = addrport.split(":", 1)
            else:
                port = addrport
        if any(a in sys.argv for a in ("--help", "-h")):
            subprocess.call([sys.executable, "-m", "daphne", "--help"])
            return
        cmd = [sys.executable, "-m", "daphne", "-b", host, "-p", port, "caufa_portal.asgi:application"]
        sys.exit(subprocess.call(cmd))

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
