"""Command-line script that creates the first administrator (like Django's createsuperuser)."""

import asyncio
import getpass
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from database.database import engine, get_postgresql_db_contextmanager
from database.models.accounts import UserGroupEnum, UserGroupModel, UserModel
from database.validators.accounts import validate_password_strength
from security.passwords import hash_password


async def create_admin(email: str, password: str) -> None:
    """
    Create an active user in the admin group.

    Args:
        email (str): Email of the new administrator.
        password (str): Plain password. It is hashed before being stored.

    Raises:
        ValueError: If a user with this email already exists, or the admin
            group is missing (migrations or startup seeding were not run).
    """
    try:
        async with get_postgresql_db_contextmanager() as session:
            existing_user = await session.scalar(
                select(UserModel).where(UserModel.email == email)
            )
            if existing_user:
                raise ValueError(f"A user with email {email} already exists.")

            admin_group = await session.scalar(
                select(UserGroupModel).where(
                    UserGroupModel.name == UserGroupEnum.ADMIN
                )
            )
            if not admin_group:
                raise ValueError(
                    "The admin group does not exist. Apply the migrations "
                    "and start the application once to seed the groups."
                )

            session.add(
                UserModel(
                    email=email,
                    hashed_password=hash_password(password),
                    is_active=True,
                    group_id=admin_group.id,
                )
            )
            await session.commit()
    finally:
        await engine.dispose()


def main() -> None:
    """
    Ask for the email and password in the terminal and create the administrator.

    The prompts are blocking, so they run here, before the async part starts.
    The password is typed twice and is not echoed.
    """
    email = input("Email: ").strip()
    try:
        TypeAdapter(EmailStr).validate_python(email)
    except ValidationError:
        sys.exit("Invalid email address.")

    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Password (again): "):
        sys.exit("Passwords do not match.")

    try:
        validate_password_strength(password)
        asyncio.run(create_admin(email, password))
    except ValueError as error:
        sys.exit(str(error))

    print(f"Administrator {email} created.")


if __name__ == "__main__":
    main()
