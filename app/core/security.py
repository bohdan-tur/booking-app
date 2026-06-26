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

def _create_jwt_token(data: dict, secret: str, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expires = datetime.now(UTC) + expires_delta
    to_encode.update({"exp": expires})
    return jwt.encode(to_encode, secret, ALGORITHM)

def _verify_jwt_token(token: str, secret: str) -> str | None:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]}
        )
        return payload.get("sub")
    except jwt.InvalidTokenError:
        return None

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    delta = expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return _create_jwt_token(data, SECRET_KEY, delta)

def create_refresh_token(data: dict) -> str:
    delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return _create_jwt_token(data, REFRESH_SECRET_KEY, delta)

def verify_access_token(token: str) -> str | None:
    return _verify_jwt_token(token, SECRET_KEY)

def verify_refresh_token(token: str) -> str | None:
    return _verify_jwt_token(token, REFRESH_SECRET_KEY)