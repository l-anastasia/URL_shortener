from pydantic import BaseModel, ConfigDict, field_validator
from pydantic_core import PydanticCustomError

import validators

class URLBase(BaseModel):
    target_url: str

    @field_validator("target_url")
    @classmethod
    def must_be_valid_url(cls, value: str) -> str:
        value = value.strip()
        if not validators.url(value):
            raise PydanticCustomError("invalid_url", "Your provided URL is not valid")
        return value

class URL(URLBase):
    is_active: bool
    clicks: int

    model_config = ConfigDict(from_attributes=True)

class URLInfo(URL):
    url: str
    admin_url: str