from pydantic import BaseModel

from database.models.accounts import UserGroupEnum


class UserChangeGroupRequestSchema(BaseModel):
    group: UserGroupEnum
