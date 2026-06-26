from datetime import timedelta
from typing import Annotated
from app.dependencies import DbSession
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, or_

from app.core.security import verify_refresh_token, create_refresh_token, create_access_token, verify_password
from app.models.user_model import Users
from app.schemas.token_schema import RefreshToken_Schema

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

    email = verify_refresh_token(token_data.refresh_token)
    query_result = await db.execute(select(Users).filter(Users.email == email))
    user = query_result.scalars().first()

    if user is None:
        raise credentials_exception

    new_access_token = create_access_token({"sub": user.email}, timedelta(minutes=15))

    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }


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

    access_token = create_access_token({"sub": user.email}, timedelta(minutes=15))
    refresh_token = create_refresh_token({"sub": user.email})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }