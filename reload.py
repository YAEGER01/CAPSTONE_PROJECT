import sys
from pathlib import Path

import uvicorn

BASE = Path(__file__).parent
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

if __name__ == "__main__":
    uvicorn.run(
        "caufa_portal.asgi:application",
        host="127.0.0.1",
        port=port,
        reload=True,
        reload_dirs=str(BASE),
    )
