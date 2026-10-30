from pydantic import BaseModel, EmailStr

from database.models.accounts import UserGroupEnum


class UserChangeGroupRequestSchema(BaseModel):
    group: UserGroupEnum


class UserActivateResendRequestSchema(BaseModel):
    email: EmailStr
