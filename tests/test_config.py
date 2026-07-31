import pytest
from pydantic import ValidationError

from app.core.config import (
    DEVELOPMENT_REFRESH_SECRET_KEY,
    DEVELOPMENT_SECRET_KEY,
    Environment,
    Settings,
)


def build_settings(**overrides) -> Settings:
    values = {
        "ENVIRONMENT": Environment.development,
        "DEBUG": False,
        "SEED_DEFAULT_USERS": False,
        "SECRET_KEY": DEVELOPMENT_SECRET_KEY,
        "REFRESH_SECRET_KEY": DEVELOPMENT_REFRESH_SECRET_KEY,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_development_uses_safe_defaults():
    settings = build_settings()

    assert settings.ENVIRONMENT is Environment.development
    assert settings.DEBUG is False
    assert settings.SEED_DEFAULT_USERS is False


def test_production_requires_non_development_secrets():
    with pytest.raises(ValidationError, match="SECRET_KEY must be set in production"):
        build_settings(ENVIRONMENT=Environment.production)


def test_production_rejects_debug():
    with pytest.raises(ValidationError, match="DEBUG must be false in production"):
        build_settings(
            ENVIRONMENT=Environment.production,
            DEBUG=True,
            SECRET_KEY="a" * 32,
            REFRESH_SECRET_KEY="b" * 32,
        )


def test_production_rejects_default_user_seeding():
    with pytest.raises(
        ValidationError, match="Default users cannot be seeded in production"
    ):
        build_settings(
            ENVIRONMENT=Environment.production,
            SEED_DEFAULT_USERS=True,
            SECRET_KEY="a" * 32,
            REFRESH_SECRET_KEY="b" * 32,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("SECRET_KEY", "too-short"),
        ("REFRESH_SECRET_KEY", "too-short"),
    ],
)
def test_rejects_short_signing_secrets(field, value):
    with pytest.raises(
        ValidationError, match=f"{field} must contain at least 32 bytes"
    ):
        build_settings(**{field: value})


def test_rejects_identical_signing_secrets():
    with pytest.raises(
        ValidationError,
        match="SECRET_KEY and REFRESH_SECRET_KEY must be different",
    ):
        build_settings(
            SECRET_KEY=DEVELOPMENT_SECRET_KEY,
            REFRESH_SECRET_KEY=DEVELOPMENT_SECRET_KEY,
        )


def test_production_accepts_safe_configuration():
    settings = build_settings(
        ENVIRONMENT=Environment.production,
        SECRET_KEY="a" * 32,
        REFRESH_SECRET_KEY="b" * 32,
    )

    assert settings.ENVIRONMENT is Environment.production
    assert settings.SECRET_KEY != DEVELOPMENT_SECRET_KEY
    assert settings.REFRESH_SECRET_KEY != DEVELOPMENT_REFRESH_SECRET_KEY
