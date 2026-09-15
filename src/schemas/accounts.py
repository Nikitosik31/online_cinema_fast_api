import re

from pydantic import BaseModel, EmailStr, field_validator


class UserRegistrationRequestSchema(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must contain at least 8 characters.")
        if not re.search(r'[A-Z]', value):
            raise ValueError("Password must contain at least one uppercase letter.")
        if not re.search(r'[a-z]', value):
            raise ValueError("Password must contain at least one lower letter.")
        if not re.search(r'\d', value):
            raise ValueError("Password must contain at least one digit.")
        if not re.search(r'[@$!%*?&#]', value):
            raise ValueError("Password must contain at least one special character: @, $, !, %, *, ?, #, &.")
        return value


class UserRegistrationResponseSchema(BaseModel):
    id: int
    email: EmailStr


class UserActivationRequestSchema(BaseModel):
    token: str


class MessageResponseSchema(BaseModel):
    message: str


class UserLoginRequestSchema(BaseModel):
    email: EmailStr
    password: str


class UserLoginResponseSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserLogoutRequestSchema(BaseModel):
    refresh_token: str
