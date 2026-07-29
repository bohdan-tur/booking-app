from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/booking"
    TEST_DATABASE_URL: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/booking_test"
    )
    REDIS_URL: str = "redis://localhost:6329/0"

    ADMIN_DEFAULT_PASSWORD: str = Field(default="dev_admin_password")
    MANAGER_DEFAULT_PASSWORD: str = Field(default="dev_manager_password")
    USER_DEFAULT_PASSWORD: str = Field(default="dev_user_password")

    SECRET_KEY: str = "dev_super_secret_key_for_access_token_generation_32_bytes"
    REFRESH_SECRET_KEY: str = (
        "dev_super_secret_key_for_refresh_token_generation_32_bytes"
    )
    ALGORITHM: str = "HS256"

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

    DEBUG: bool = True
    TESTING: bool = False

    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,
    )


settings = Settings()
