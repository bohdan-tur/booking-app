from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    development = "development"
    test = "test"
    production = "production"


DEVELOPMENT_SECRET_KEY = "dev_super_secret_key_for_access_token_generation_32_bytes"
DEVELOPMENT_REFRESH_SECRET_KEY = (
    "dev_super_secret_key_for_refresh_token_generation_32_bytes"
)
MIN_SECRET_KEY_BYTES = 32


class Settings(BaseSettings):
    ENVIRONMENT: Environment = Environment.development

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/booking"
    TEST_DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/booking_test"
    )
    REDIS_URL: str = "redis://localhost:6329/0"

    ADMIN_DEFAULT_PASSWORD: str = Field(default="dev_admin_password")
    MANAGER_DEFAULT_PASSWORD: str = Field(default="dev_manager_password")
    USER_DEFAULT_PASSWORD: str = Field(default="dev_user_password")
    SEED_DEFAULT_USERS: bool = False

    SECRET_KEY: str = DEVELOPMENT_SECRET_KEY
    REFRESH_SECRET_KEY: str = DEVELOPMENT_REFRESH_SECRET_KEY
    ALGORITHM: Literal["HS256"] = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = "test_user"
    SMTP_PASSWORD: str = "test_password"
    SMTP_TIMEOUT: int = 10
    EMAIL_FROM: str = "noreply@example.com"

    TIMEZONE: str = "UTC"
    SUPPORT_EMAIL: str = "support@example.com"
    SUPPORT_PHONE: str = "+1234567890"

    DEBUG: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        secrets = {
            "SECRET_KEY": self.SECRET_KEY,
            "REFRESH_SECRET_KEY": self.REFRESH_SECRET_KEY,
        }

        for name, value in secrets.items():
            if len(value.encode("utf-8")) < MIN_SECRET_KEY_BYTES:
                raise ValueError(
                    f"{name} must contain at least {MIN_SECRET_KEY_BYTES} bytes"
                )

        if self.SECRET_KEY == self.REFRESH_SECRET_KEY:
            raise ValueError("SECRET_KEY and REFRESH_SECRET_KEY must be different")

        if self.ENVIRONMENT is Environment.production:
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production")
            if self.SEED_DEFAULT_USERS:
                raise ValueError("Default users cannot be seeded in production")
            if self.SECRET_KEY == DEVELOPMENT_SECRET_KEY:
                raise ValueError("SECRET_KEY must be set in production")
            if self.REFRESH_SECRET_KEY == DEVELOPMENT_REFRESH_SECRET_KEY:
                raise ValueError("REFRESH_SECRET_KEY must be set in production")

        return self


settings = Settings()
