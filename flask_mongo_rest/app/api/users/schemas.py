
from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional

class UserCreate(BaseModel):
    user_name: str = Field(min_length=1, max_length=120)
    password_user: str = Field(min_length=6, max_length=120)
    role_name: str = Field(min_length=1, max_length=50)

class UserUpdate(BaseModel):
    user_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    password: Optional[str]  = Field(default=None, min_length=6, max_length=120)
    role_name: Optional[str] = Field(default=None, min_length=1, max_length=50)

    @model_validator(mode="after")
    def at_least_one(self):
        if not any([self.user_name, self.password, self.role_name]):
            raise ValueError("At least one of user_name, password, role_name is required")
        return self

class UserOut(BaseModel):
    id: str
    username: str
    role_name: Optional[str] = None
    is_active: bool