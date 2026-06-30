from datetime import timedelta
from typing import Annotated
from app.dependencies import DbSession
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, or_
from app.core.config import settings
from app.core.security import verify_refresh_token, create_refresh_token, create_access_token, verify_password
from app.models.user_model import Users
from app.schemas.token_schema import RefreshToken_Schema
from app.schemas.user_schema import UserCreate, UserOut
from app.core.security import hash_password


router = APIRouter(tags=['Auth'])

@router.post(
    "/",
    status_code=status.HTTP_200_OK)
async def get_refresh_token(db: DbSession, token_data: RefreshToken_Schema):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"}
    )

    user_id_str = verify_refresh_token(token_data.refresh_token)

    if not user_id_str:
        raise credentials_exception

    query_result = await db.execute(select(Users).filter(Users.id == int(user_id_str)))
    user = query_result.scalars().first()

    if user is None:
        raise credentials_exception

    new_access_token = create_access_token({"sub": str(user.id)}, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    new_refresh_token = create_refresh_token({"sub": str(user.id)})

    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer"
    }





@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def add_user(user_data: UserCreate, db: DbSession):
    query_result = await db.execute(select(Users).filter(Users.email == user_data.email))

    if query_result.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User with this email already exists")

    hashed_pwd = hash_password(user_data.password)
    new_user = Users(
        username=user_data.username,
        password_hash=hashed_pwd,
        email=user_data.email,
        is_active=True
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user






@router.post(
    '/login',
    status_code=status.HTTP_200_OK
)
async def user_login(
    user_credentials: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession
):
    query_result = await db.execute(select(Users).filter(
        or_(
            Users.email == user_credentials.username,
            Users.username == user_credentials.username
        )
    ))
    user = query_result.scalars().first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = create_access_token({"sub": str(user.id)}, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    refresh_token = create_refresh_token({"sub": str(user.id)})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }