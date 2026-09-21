import argparse
from urllib.parse import quote

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.identity import create_recovery_grant
from app.models import User, UserRole


def run() -> None:
    parser = argparse.ArgumentParser(prog="haus-admin")
    subparsers = parser.add_subparsers(dest="command", required=True)
    recovery_parser = subparsers.add_parser(
        "recovery-token",
        help="create a short-lived administrator recovery URL",
    )
    recovery_parser.add_argument("--email", required=True)
    args = parser.parse_args()

    if args.command == "recovery-token":
        with SessionLocal() as session:
            administrator = session.scalar(
                select(User).where(
                    User.email == args.email,
                    User.role == UserRole.ADMINISTRATOR.value,
                    User.is_active.is_(True),
                )
            )
            if administrator is None:
                parser.error("active administrator was not found")
            token = create_recovery_grant(session, administrator=administrator)
            session.commit()

        settings = get_settings()
        print(
            "Recovery URL (valid for 10 minutes; single use): "
            f"https://{settings.household_hostname}/auth/recovery?token={quote(token)}"
        )