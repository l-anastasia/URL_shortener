from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, SecretStr, EmailStr 
from pydantic_core import PydanticCustomError
from datetime import datetime

import validators
from zxcvbn import zxcvbn


MIN_PASSWORD_SCORE = 3   # zxcvbn: 0 = too guessable … 4 = very unguessable


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
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class URLInfo(URL):
    url: str
    admin_url: str

class UserCreate(BaseModel):
    username: str = Field(min_length=5, max_length=15, pattern=r"^[a-z0-9_]+$")
    email: EmailStr | None = None
    password: SecretStr  = Field(min_length=8, max_length=64)
    confirm_password: SecretStr 

    @field_validator("email", mode="before")
    @classmethod
    def empty_email_is_none(cls, value):
        # An empty form field arrives as "", which isn't a valid email. Treat it as "no email".
        if isinstance(value, str):
            value = value.strip().lower()
        return value or None

    @model_validator(mode="after")
    def password_strong_enough(self):
        password = self.password.get_secret_value()

        if self.username in password.lower():
            raise PydanticCustomError(
                "password_contains_username",
                "Your password must not contain your username.",
            )

        result = zxcvbn(password, user_inputs=[self.username, self.email or ""])
        if result["score"] < MIN_PASSWORD_SCORE:
            feedback = result["feedback"]
            hint = feedback["warning"] or " ".join(feedback["suggestions"])
            raise PydanticCustomError(
                "weak_password",
                "This password is too easy to guess. {hint}",
                {"hint": hint},
            )
        return self
    
    @model_validator(mode="after")
    def password_match(self):
        if self.password.get_secret_value() != self.confirm_password.get_secret_value():
            raise PydanticCustomError("password_mismatch", "Passwords don't match")
        return self