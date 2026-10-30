"""Abstract interface for the JWT manager (allows swapping the implementation in tests)."""

from abc import ABC, abstractmethod
from datetime import timedelta


class JWTAuthManagerInterface(ABC):
    """
    Interface for JWT Authentication Manager.
    Defines methods for creating, decoding, and verifying JWT tokens.
    """

    @abstractmethod
    def create_access_token(
        self, data: dict, expires_delta: timedelta | None = None
    ) -> str:
        """
        Create a new access token.
        """
        pass

    @abstractmethod
    def decode_access_token(self, token: str) -> dict:
        """
        Decode and validate an access token.
        """
        pass
