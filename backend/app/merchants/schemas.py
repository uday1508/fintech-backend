import uuid
import re

from pydantic import BaseModel, Field, field_validator

_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,50}$")


class MerchantCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    username: str = Field(min_length=3, max_length=50)
    category_id: uuid.UUID

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _USERNAME_PATTERN.fullmatch(normalized):
            raise ValueError("Business username must be 3-50 letters, numbers, underscores, or hyphens")
        return normalized


