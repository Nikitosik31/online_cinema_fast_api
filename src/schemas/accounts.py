from pydantic import BaseModel, EmailStr, field_validator

from database.validators.accounts import validate_password_strength


class UserRegistrationRequestSchema(BaseModel):
    """
    Data for registering a new account.

    The password must be at least 8 characters long and contain an uppercase
    letter, a lowercase letter, a digit and a special character (@ $ ! % * ? # &).
    """

    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UserRegistrationResponseSchema(BaseModel):
    id: int
    email: EmailStr


class UserActivationRequestSchema(BaseModel):
    token: str


class MessageResponseSchema(BaseModel):
    message: str


class UserActivationResendRequestSchema(BaseModel):
    email: EmailStr


class UserLoginRequestSchema(BaseModel):
    email: EmailStr
    password: str


class UserLoginResponseSchema(BaseModel):
    """
    Tokens issued after a successful login.

    Send `access_token` in the `Authorization: Bearer` header. When it
    expires, exchange `refresh_token` for a new one.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserLogoutRequestSchema(BaseModel):
    refresh_token: str


class TokenRefreshRequestSchema(BaseModel):
    refresh_token: str


class TokenRefreshResponseSchema(BaseModel):
    access_token: str


class UserChangePasswordRequestSchema(BaseModel):
    """
    Old password for confirmation and the new one
    (must meet the same strength rules as at registration).
    """

    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)


class UserResetPasswordRequestSchema(BaseModel):
    email: EmailStr


class UserPasswordResetConfirmRequestSchema(BaseModel):
    """
    The token from the reset email and the new password
    (must meet the same strength rules as at registration).
    """

    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return validate_password_strength(value)
