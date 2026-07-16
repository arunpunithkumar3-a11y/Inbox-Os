from pydantic import BaseModel, Field, EmailStr
from typing import List


class UserSignup(BaseModel):
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=6, max_length=128)
    user_name: str = Field(min_length=1, max_length=50)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleLogin(BaseModel):
    email: str
    access_token: str
    refresh_token: str
    token_expiry: str
    scope: List[str]
