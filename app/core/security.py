from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from .config import settings

password_hash = PasswordHash.recommended()

ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY
REFRESH_SECRET_KEY = settings.REFRESH_SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


@dataclass(frozen=True, slots=True)
class VerifiedToken:
    user_id: int
    issued_at: datetime


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)


def _create_jwt_token(
    data: dict,
    secret: str,
    expires_delta: timedelta,
    token_type: str,
) -> str:
    to_encode = data.copy()
    issued_at = datetime.now(UTC)
    to_encode.update(
        {
            "exp": issued_at + expires_delta,
            "iat": issued_at.timestamp(),
            "type": token_type,
        }
    )
    return jwt.encode(to_encode, secret, ALGORITHM)


def _verify_jwt_token(
    token: str,
    secret: str,
    expected_type: str,
) -> VerifiedToken | None:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "iat", "sub", "type"]},
        )
        if payload["type"] != expected_type:
            return None

        user_id = int(payload["sub"])
        if user_id <= 0:
            return None

        issued_at = datetime.fromtimestamp(payload["iat"], UTC)
        return VerifiedToken(user_id=user_id, issued_at=issued_at)
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError, OverflowError):
        return None


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    delta = (
        expires_delta
        if expires_delta
        else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return _create_jwt_token(data, SECRET_KEY, delta, ACCESS_TOKEN_TYPE)


def create_refresh_token(data: dict) -> str:
    delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_jwt_token(data, REFRESH_SECRET_KEY, delta, REFRESH_TOKEN_TYPE)


def verify_access_token(token: str) -> VerifiedToken | None:
    return _verify_jwt_token(token, SECRET_KEY, ACCESS_TOKEN_TYPE)


def verify_refresh_token(token: str) -> VerifiedToken | None:
    return _verify_jwt_token(token, REFRESH_SECRET_KEY, REFRESH_TOKEN_TYPE)


def is_token_invalidated(
    token: VerifiedToken,
    tokens_valid_after: datetime | None,
) -> bool:
    return tokens_valid_after is not None and token.issued_at < tokens_valid_after
