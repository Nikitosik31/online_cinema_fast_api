from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt, ExpiredSignatureError

from exceptions.security import TokenExpiredError, InvalidTokenError
from security.jwt_interfaces import JWTAuthManagerInterface


class JWTAuthManager(JWTAuthManagerInterface):
    """
    A manager for creating, decoding, and verifying JWT access and refresh tokens.
    """

    _ACCESS_TOKEN_EXPIRE_MINUTES = 60

    def __init__(self, secret_key_access: str, algorithm: str):
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

    def create_access_token(self, data: dict, expires_delta: timedelta = None):
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
