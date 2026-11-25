"""Run from backend/: python ../scripts/manage_users.py create USERNAME or import-local."""

import argparse
import getpass
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.core.config import get_settings
from app.db.session import session_factory
from app.modules.auth.local import password_hash
from app.modules.auth.models import User
from sqlalchemy import select

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("action", choices=["create", "import-local", "list"])
parser.add_argument("username", nargs="?")
a = parser.parse_args()
with session_factory().begin() as session:
    if a.action == "list":
        for user in session.scalars(select(User).order_by(User.username)):
            print(user.username, "enabled" if user.enabled else "disabled")
    else:
        cfg = get_settings()
        name = cfg.login_username if a.action == "import-local" else a.username
        if not name or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", name):
            raise SystemExit(
                "Username: 1-100 ASCII letters, numbers, underscore or hyphen"
            )
        if session.scalar(select(User).where(User.username == name)):
            raise SystemExit("Account already exists; no changes made")
        if a.action == "import-local":
            encoded = cfg.login_password_hash
            if not encoded:
                raise SystemExit("No local password hash configured")
        else:
            password = getpass.getpass("Password (12+ characters): ")
            if len(password) < 12 or password != getpass.getpass("Confirm password: "):
                raise SystemExit("Passwords must match and contain 12+ characters")
            encoded = password_hash(password)
        session.add(User(username=name, password_hash=encoded))
        print("Created account:", name)
