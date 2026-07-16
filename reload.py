import sys
from pathlib import Path

import uvicorn

BASE = Path(__file__).parent
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

if __name__ == "__main__":
    print(f"[reload] Watching: {BASE}")
    print(f"[reload] Use Ctrl+C to stop")
    uvicorn.run(
        "caufa_portal.asgi:application",
        host="127.0.0.1",
        port=port,
        reload=True,
        reload_dirs=[str(BASE)],
        reload_includes=[
            "*.py",
            "*.html",
            "*.js",
            "*.css",
            "*.json",
            "*.txt",
            "*.yml",
            "*.yaml",
            "*.toml",
            "*.env",
        ],
        reload_excludes=[
            "*.pyc",
            "*.pyo",
            "__pycache__",
            ".git",
            ".venv",
            "venv",
            "node_modules",
            ".migrations",
            "*.log",
            "*.sqlite3",
            "*.db",
        ],
    )
