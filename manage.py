#!/usr/bin/env python
import os
import runpy
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.join(ROOT, "CAPSTONE_PROJECT-panel-system-dev")

if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

os.chdir(PROJECT_DIR)

if __name__ == "__main__":
    sys.argv[0] = os.path.join(PROJECT_DIR, "manage.py")
    runpy.run_path(os.path.join(PROJECT_DIR, "manage.py"), run_name="__main__")
