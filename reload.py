import subprocess, sys
from pathlib import Path

import watchfiles

BASE = Path(__file__).parent

def run_server():
    proc = subprocess.run(
        [sys.executable, "-m", "daphne", "-b", "127.0.0.1", "-p", sys.argv[1] if len(sys.argv) > 1 else "5000", "caufa_portal.asgi:application"],
        cwd=BASE,
    )
    if proc.returncode != 0:
        print(f"[CRASH] Daphne exited with code {proc.returncode} — restarting in 3s...", file=sys.stderr)
        import time
        time.sleep(3)

if __name__ == "__main__":
    watchfiles.run_process(str(BASE), target=run_server)
