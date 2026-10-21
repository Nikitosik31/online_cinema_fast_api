from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt, ExpiredSignatureError

from exceptions.security import TokenExpiredError, InvalidTokenError
from security.jwt_interfaces import JWTAuthManagerInterface


class JWTAuthManager(JWTAuthManagerInterface):
    """
    A manager for creating and decoding JWT access tokens.

    Refresh tokens are not JWTs in this project: they are random strings
    stored in the database.
    """

    _ACCESS_TOKEN_EXPIRE_MINUTES = 60

    def __init__(self, secret_key_access: str, algorithm: str) -> None:
        """
        Args:
            secret_key_access (str): Secret used to sign and verify access tokens.
            algorithm (str): JWT signing algorithm, for example "HS256".
        """

        self._secret_key_access = secret_key_access
        self._algorithm = algorithm

    def _create_token(
        self, data: dict, secret_key: str, expires_delta: timedelta
    ) -> str:
        """
        Create a JWT token with provided data, secret key, and expiration time.
        """
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + expires_delta
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, secret_key, algorithm=self._algorithm)

    def create_access_token(
        self, data: dict, expires_delta: timedelta | None = None
    ) -> str:
        """
        Create a signed JWT access token.

        Args:
            data (dict): Claims to store in the token (we put the user id in `sub`).
            expires_delta (timedelta | None): Token lifetime. Defaults to
                60 minutes (`_ACCESS_TOKEN_EXPIRE_MINUTES`).

        Returns:
            str: The encoded token. An `exp` claim is added automatically.
        """

        return self._create_token(
            data,
            self._secret_key_access,
            expires_delta
            or timedelta(minutes=self._ACCESS_TOKEN_EXPIRE_MINUTES),
        )

    def decode_access_token(self, token: str) -> dict:
        """
        Decode and validate an access token, returning the token's data.
        """
        try:
            return jwt.decode(
                token, self._secret_key_access, algorithms=[self._algorithm]
            )
        except ExpiredSignatureError:
            raise TokenExpiredError
        except JWTError:
            raise InvalidTokenError
