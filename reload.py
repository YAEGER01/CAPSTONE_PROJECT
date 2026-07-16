import sys
from pathlib import Path

import uvicorn

BASE = Path(__file__).parent
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
do_reload = len(sys.argv) > 2 and sys.argv[2] == "--reload"

if __name__ == "__main__":
    kwargs = {
        "host": "127.0.0.1",
        "port": port,
        "reload_dirs": [str(BASE)] if do_reload else None,
    }
    if do_reload:
        print(f"[reload] Watching: {BASE}")
        kwargs["reload"] = True
        kwargs["reload_includes"] = [
            "*.py", "*.html", "*.js", "*.css", "*.json", "*.txt",
            "*.yml", "*.yaml", "*.toml", "*.env",
        ]
        kwargs["reload_excludes"] = [
            "*.pyc", "*.pyo", "__pycache__", ".git", ".venv",
            "venv", "node_modules", ".migrations", "*.log",
            "*.sqlite3", "*.db",
        ]
    else:
        print(f"[reload] No file watching (use -NoReload to enable)")
    print(f"[reload] Use Ctrl+C to stop")
    uvicorn.run("caufa_portal.asgi:application", **kwargs)
