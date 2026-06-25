import jwt
from datetime import timedelta, datetime, UTC
from passlib.context import CryptContext
from .config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated='auto')

ALGORITHM = settings.ALGORITHM
SECRET_KEY = settings.SECRET_KEY
REFRESH_SECRET_KEY = settings.REFRESH_SECRET_KEY
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS


def hash_password(password: str) -> str:

    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expires = datetime.now(UTC) + expires_delta
    else:
        expires = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expires})
    encode_jwt = jwt.encode(to_encode, SECRET_KEY, ALGORITHM)
    return encode_jwt


def verify_access_token(token: str) -> str | None:
    try:

        payload = jwt.decode(token,
                             SECRET_KEY,
                             algorithms=[ALGORITHM],
                             options={"require": ["exp", "sub"]})
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None


def create_refresh_token(data: dict):
    encoded_data = data.copy()
    expires_time = datetime.now(UTC) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    encoded_data.update({"exp": expires_time})

    encoded_jwt = jwt.encode(encoded_data, REFRESH_SECRET_KEY, ALGORITHM)
    return encoded_jwt


def verify_refresh_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token,
                             REFRESH_SECRET_KEY,
                             algorithms=[ALGORITHM],
                             options={"require": ["exp", "sub"]})
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None