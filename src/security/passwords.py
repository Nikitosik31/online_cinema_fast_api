"""Password hashing and verification (bcrypt)."""

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a plain password with bcrypt.

    Args:
        password (str): The plain-text password.

    Returns:
        str: The hash to store in the database. The plain password is never stored.
    """

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Check a plain password against a stored hash.

    Args:
        plain_password (str): The password entered by the user.
        hashed_password (str): The hash stored in the database.

    Returns:
        bool: True if the password matches the hash, otherwise False.
    """

    return pwd_context.verify(plain_password, hashed_password)
