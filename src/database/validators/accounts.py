"""Reusable validators for account data."""

import re


def validate_password_strength(password: str) -> str:
    """
    Check that a password is strong enough.

    Rules: at least 8 characters, and at least one uppercase letter, one
    lowercase letter, one digit and one special character (@ $ ! % * ? # &).

    Args:
        password (str): The password to check.

    Returns:
        str: The same password, if it passes all checks.

    Raises:
        ValueError: With a message describing the first rule that failed.
    """

    if len(password) < 8:
        raise ValueError("Password must contain at least 8 characters.")
    if not re.search(r"[A-Z]", password):
        raise ValueError(
            "Password must contain at least one uppercase letter."
        )
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lower letter.")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit.")
    if not re.search(r"[@$!%*?&#]", password):
        raise ValueError(
            "Password must contain at least one special character: @, $, !, %, *, ?, #, &."
        )
    return password
