"""Reset one user's password from an authorized local terminal.

The password is read with ``getpass`` so it is not echoed, stored in shell
history, or accepted as a command-line argument.

Usage:
    python scripts/reset_user_password.py user@example.com
"""

import argparse
import asyncio
import getpass
import sys
from pathlib import Path

from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.auth.security import hash_password, verify_password  # noqa: E402
from src.db.models import User  # noqa: E402
from src.db.session import async_session_maker  # noqa: E402


def _read_password() -> str:
    password = getpass.getpass("New password: ")
    if len(password) < 6:
        raise SystemExit("Password must be at least 6 characters.")
    confirmation = getpass.getpass("Confirm new password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    return password


async def _reset_password(email: str, password: str) -> bool:
    async with async_session_maker() as db:
        user = (
            await db.execute(select(User).where(func.lower(User.email) == email.strip().lower()))
        ).scalar_one_or_none()
        if user is None:
            return False

        user.password_hash = hash_password(password)
        await db.commit()
        await db.refresh(user)
        if not verify_password(password, user.password_hash):
            raise RuntimeError("Password verification failed after saving")
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset an Orbit user's password")
    parser.add_argument("email", help="Email address of the account to reset")
    args = parser.parse_args()

    password = _read_password()
    if not asyncio.run(_reset_password(args.email, password)):
        raise SystemExit(f"No account found for {args.email}")
    print(f"Password reset successfully for {args.email}")


if __name__ == "__main__":
    main()
