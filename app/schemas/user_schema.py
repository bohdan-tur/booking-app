from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class UserCreate(UserBase):
    username: str
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    username: str
    role: str


class UserPasswordUpdate(BaseModel):
    new_password: str = Field(min_length=8)


class UserRoleUpdate(BaseModel):
    role: str
