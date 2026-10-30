from datetime import date

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from database.models.accounts import GenderEnum


class ProfileResponseSchema(BaseModel):
    first_name: str | None
    last_name: str | None
    gender: GenderEnum | None
    date_of_birth: date | None
    info: str | None
    avatar_url: str | None = Field(
        default=None,
        description="Public URL of the avatar, or null if there is none",
        examples=["http://localhost:9000/avatars/avatars/7/3f2a.jpg"],
    )

    model_config = ConfigDict(from_attributes=True)


class ProfileUpdateRequestSchema(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=50)
    last_name: str | None = Field(default=None, min_length=1, max_length=50)
    gender: GenderEnum | None = None
    date_of_birth: date | None = None
    info: str | None = Field(default=None, max_length=1000)

    @field_validator("date_of_birth")
    @classmethod
    def date_of_birth_validator(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("Date of birth cannot be in the future")
        return value
