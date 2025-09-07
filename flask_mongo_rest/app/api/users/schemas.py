
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=120)

class UserOut(BaseModel):
    id: str
    name: str
    email: EmailStr
