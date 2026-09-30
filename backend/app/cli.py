"""Staff account management.

    .venv\\Scripts\\python -m app.cli create-user --username asha --name "Dr Asha Rao" --role reviewer
    .venv\\Scripts\\python -m app.cli demo-users     # curator + reviewer with random passwords

Passwords are typed at a hidden prompt (create-user) or generated and written to
data/demo_users.local.txt (demo-users); that file is gitignored. They are never printed.
"""
import argparse
import getpass
import secrets

from sqlalchemy import select

from app.core.config import DATA_DIR
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import User
from app.models.content import ROLES
from app.services import audit


def upsert_user(username: str, display_name: str, role: str, password: str) -> None:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        created = user is None
        user = user or User(username=username)
        user.display_name, user.role, user.password_hash, user.is_active = display_name, role, hash_password(password), True
        db.add(user)
        db.flush()
        audit.record(db, "system:cli", "user_created" if created else "user_updated", "user", user.id, role=role)
        db.commit()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create-user")
    c.add_argument("--username", required=True)
    c.add_argument("--name", required=True, help="display name recorded on approvals")
    c.add_argument("--role", required=True, choices=ROLES)
    sub.add_parser("demo-users")
    args = ap.parse_args()

    if args.cmd == "create-user":
        password = getpass.getpass("Password: ")
        if len(password) < 10 or password != getpass.getpass("Repeat: "):
            raise SystemExit("Passwords must match and be at least 10 characters.")
        upsert_user(args.username, args.name, args.role, password)
        print(f"User {args.username} ({args.role}) saved.")
    else:
        lines = ["# Demo staff accounts for the local prototype. Gitignored; do not reuse these passwords.\n"]
        for username, name, role in [("curator", "Demo Curator", "curator"), ("reviewer", "Demo Reviewer", "reviewer")]:
            password = secrets.token_urlsafe(12)
            upsert_user(username, name, role, password)
            lines.append(f"{role}: username={username} password={password}\n")
        out = DATA_DIR / "demo_users.local.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("".join(lines), encoding="utf-8")
        print(f"Demo users saved. Their passwords are in {out}")


if __name__ == "__main__":
    main()
