from pydantic import BaseModel, EmailStr, Field, field_validator
from datetime import datetime
from typing import Optional, Literal


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def bcrypt_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    has_github_token: bool = False
    llm_provider: str = "gemini"
    created_at: datetime

    class Config:
        from_attributes = True


class UserSettingsUpdate(BaseModel):
    name: Optional[str] = None
    # Send an empty string to clear the token
    github_token: Optional[str] = None
    llm_provider: Optional[Literal["gemini", "groq"]] = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
