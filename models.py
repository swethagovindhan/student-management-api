from pydantic import BaseModel, Field
from typing import Optional


class StudentBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Full name of the student")
    email: str = Field(..., description="Unique email address")
    age: int = Field(..., ge=1, le=120, description="Age of the student")
    grade: str = Field(..., min_length=1, max_length=10, description="Grade or year level")


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = Field(None)
    age: Optional[int] = Field(None, ge=1, le=120)
    grade: Optional[str] = Field(None, min_length=1, max_length=10)


class StudentResponse(StudentBase):
    id: int
    created_at: str

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50, description="Unique username")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    id: int
    username: str
    created_at: str
