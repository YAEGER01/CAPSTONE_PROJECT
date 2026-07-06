import sys
from pathlib import Path

import uvicorn
from django.core.management.base import BaseCommand, CommandParser


class Command(BaseCommand):
    help = "Run the ASGI server (uvicorn) with auto-reload and WebSocket support."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "addrport", nargs="?", default="8000",
            help="Optional port number, or ipaddr:port (default 8000).",
        )
        parser.add_argument(
            "--ipv6", "-6", action="store_true", default=False,
            help="Use IPv6.",
        )

    def handle(self, *args, **options) -> None:
        addrport = options["addrport"]
        use_ipv6 = options["ipv6"]

        if ":" in addrport:
            host, port_str = addrport.split(":", 1)
        else:
            host = "::1" if use_ipv6 else "127.0.0.1"
            port_str = addrport

        try:
            port = int(port_str)
        except ValueError:
            self.stderr.write(self.style.ERROR(f"Invalid port: {port_str}"))
            sys.exit(1)

        base_dir = Path(__file__).resolve().parent.parent.parent.parent

        self.stdout.write(self.style.SUCCESS(
            f"Starting ASGI server at http://{host}:{port}/"
        ))
        self.stdout.write(self.style.WARNING(
            "Quit the server with CTRL-BREAK."
        ))

        uvicorn.run(
            "caufa_portal.asgi:application",
            host=host,
            port=port,
            reload=True,
            reload_dirs=str(base_dir),
        )
