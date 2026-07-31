from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import or_, select

from app.api.dependencies import DbSession, get_current_user
from app.core.config import settings
from app.core.security import (
    create_access_token,
    hash_password,
    is_token_invalidated,
    verify_password,
    verify_refresh_token,
)
from app.models.user_model import User
from app.schemas.token_schema import RefreshTokenRequest
from app.schemas.user_schema import MAX_PASSWORD_LENGTH, UserCreate, UserOut
from app.services.rate_limit_service import RateLimitExceeded, enforce_rate_limit
from app.services.refresh_token_service import (
    InvalidRefreshTokenError,
    RefreshTokenService,
)

router = APIRouter(tags=["Auth"])

DUMMY_PASSWORD_HASH = hash_password("dummy_password_used_for_timing_consistency")
LOGIN_IP_LIMIT = 10
LOGIN_ACCOUNT_LIMIT = 5
REGISTRATION_IP_LIMIT = 3
REFRESH_IP_LIMIT = 10


def _client_ip(request: Request) -> str:
    return request.client.host if request.client is not None else "unknown"


async def _enforce_auth_rate_limit(
    bucket: str,
    identifier: str,
    limit: int,
) -> None:
    try:
        await enforce_rate_limit(bucket, identifier, limit)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests",
            headers={"Retry-After": str(exc.retry_after)},
        ) from None


@router.post("/refresh", status_code=status.HTTP_200_OK)
async def get_refresh_token(
    request: Request,
    db: DbSession,
    token_data: RefreshTokenRequest,
) -> dict[str, str]:
    await _enforce_auth_rate_limit(
        "refresh-ip",
        _client_ip(request),
        REFRESH_IP_LIMIT,
    )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    verified_token = verify_refresh_token(token_data.refresh_token)

    if verified_token is None:
        raise credentials_exception

    query_result = await db.execute(
        select(User).filter(User.id == verified_token.user_id)
    )
    user = query_result.scalars().first()

    if user is None or is_token_invalidated(verified_token, user.tokens_valid_after):
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact support.",
        )

    try:
        new_refresh_token = await RefreshTokenService(db).rotate(
            token_data.refresh_token,
            user.id,
        )
    except InvalidRefreshTokenError:
        raise credentials_exception from None

    new_access_token = create_access_token(
        {"sub": str(user.id)}, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {
        "access_token": new_access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserOut)
async def add_user(
    request: Request,
    user_data: UserCreate,
    db: DbSession,
) -> UserOut:
    await _enforce_auth_rate_limit(
        "registration-ip",
        _client_ip(request),
        REGISTRATION_IP_LIMIT,
    )

    query_result = await db.execute(
        select(User).filter(User.email == user_data.email)
    )

    if query_result.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    hashed_pwd = hash_password(user_data.password)
    new_user = User(
        username=user_data.username,
        password_hash=hashed_pwd,
        email=user_data.email,
        is_active=True,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.post("/login", status_code=status.HTTP_200_OK)
async def user_login(
    request: Request,
    user_credentials: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> dict[str, str]:
    login = user_credentials.username
    await _enforce_auth_rate_limit(
        "login-ip",
        _client_ip(request),
        LOGIN_IP_LIMIT,
    )
    await _enforce_auth_rate_limit(
        "login-account",
        login.lower(),
        LOGIN_ACCOUNT_LIMIT,
    )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if len(user_credentials.password) > MAX_PASSWORD_LENGTH:
        raise credentials_exception

    query_result = await db.execute(
        select(User).filter(
            or_(
                User.email == login.lower(),
                User.username == login,
            )
        )
    )
    user = query_result.scalars().first()

    password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
    password_is_valid = verify_password(user_credentials.password, password_hash)

    if user is None or not password_is_valid:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated. Please contact support.",
        )

    access_token = create_access_token(
        {"sub": str(user.id)}, timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = await RefreshTokenService(db).create(user.id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(token_data: RefreshTokenRequest, db: DbSession) -> None:
    verified_token = verify_refresh_token(token_data.refresh_token)
    if verified_token is not None:
        await RefreshTokenService(db).revoke(
            token_data.refresh_token,
            verified_token.user_id,
        )


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(
    db: DbSession,
    user: Annotated[User, Depends(get_current_user)],
) -> None:
    user.tokens_valid_after = datetime.now(UTC)
    await RefreshTokenService(db).revoke_all(user.id)
