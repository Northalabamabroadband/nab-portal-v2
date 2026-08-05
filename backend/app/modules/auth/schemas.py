from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class SessionUser(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    roles: list[str]
    permissions: list[str]
    is_superuser: bool


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user: SessionUser
