"""Compatibility entry point for creating a persistent database account."""

import runpy
import sys
from pathlib import Path

username = input("New username [thesis]: ").strip() or "thesis"
sys.argv = ["manage_users.py", "create", username]
runpy.run_path(str(Path(__file__).with_name("manage_users.py")), run_name="__main__")
