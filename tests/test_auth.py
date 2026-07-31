import asyncio

from httpx import AsyncClient
from sqlalchemy import select

from app.api.routers import auth as auth_router
from app.models.refresh_token_model import RefreshToken
from app.models.user_model import User
from app.services.rate_limit_service import RateLimitExceeded
from app.services.refresh_token_service import hash_refresh_token


async def register_and_login(
    client: AsyncClient,
    *,
    username: str,
    email: str,
    password: str = "password12345",
) -> dict[str, str]:
    registration = await client.post(
        "/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    assert registration.status_code == 201

    login = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login.status_code == 200
    return login.json()


async def test_register_user_success(client: AsyncClient):
    payload = {
        "username": "BohdanSuccess",
        "email": "bohdan_success@example.com",
        "password": "password12345",
    }
    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 201
    assert response.json()["email"] == payload["email"]


async def test_login_user_by_email(client: AsyncClient):
    payload = {
        "username": "LoginEmailUser",
        "email": "login_email@example.com",
        "password": "password12345",
    }
    await client.post("/auth/register", json=payload)

    login_data = {"username": payload["email"], "password": payload["password"]}
    response = await client.post("/auth/login", data=login_data)

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


async def test_login_user_by_username(client: AsyncClient):
    payload = {
        "username": "LoginUsernameUser",
        "email": "login_username@example.com",
        "password": "password12345",
    }
    await client.post("/auth/register", json=payload)

    login_data = {"username": payload["username"], "password": payload["password"]}
    response = await client.post("/auth/login", data=login_data)

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_refresh_token_success(client: AsyncClient):
    payload = {
        "username": "RefreshUser",
        "email": "refresh@example.com",
        "password": "password12345",
    }
    await client.post("/auth/register", json=payload)

    login_data = {"username": payload["email"], "password": payload["password"]}
    login_response = await client.post("/auth/login", data=login_data)
    refresh_token = login_response.json()["refresh_token"]

    refresh_payload = {"refresh_token": refresh_token}

    response = await client.post("/auth/refresh", json=refresh_payload)

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()

    old_token_response = await client.post("/auth/refresh", json=refresh_payload)
    assert old_token_response.status_code == 401


async def test_login_wrong_password(client: AsyncClient):
    payload = {
        "username": "WrongPassUser",
        "email": "wrong_pass@example.com",
        "password": "CorrectPassword123",
    }
    await client.post("/auth/register", json=payload)

    login_data = {"username": payload["email"], "password": "WrongPassword123"}
    response = await client.post("/auth/login", data=login_data)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_login_nonexistent_user(client: AsyncClient):
    login_data = {
        "username": "nobody_exists@example.com",
        "password": "SomePassword123",
    }
    response = await client.post("/auth/login", data=login_data)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_register_duplicate_user(client: AsyncClient):
    payload = {
        "username": "DuplicateUser",
        "email": "duplicate@example.com",
        "password": "password12345",
    }

    response1 = await client.post("/auth/register", json=payload)
    assert response1.status_code == 201

    response2 = await client.post("/auth/register", json=payload)
    assert response2.status_code == 400
    assert response2.json()["detail"] == "User with this email already exists"


async def test_refresh_token_invalid(client: AsyncClient):
    refresh_payload = {"refresh_token": "fake.invalid.token"}

    response = await client.post("/auth/refresh", json=refresh_payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate refresh token"


async def test_login_stores_only_refresh_token_hash(
    client: AsyncClient,
    db_session,
):
    tokens = await register_and_login(
        client,
        username="StoredHashUser",
        email="stored_hash@example.com",
    )

    stored_session = await db_session.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_refresh_token(tokens["refresh_token"])
        )
    )

    assert stored_session is not None
    assert stored_session.token_hash != tokens["refresh_token"]
    assert len(stored_session.token_hash) == 64


async def test_access_and_refresh_tokens_are_not_interchangeable(
    client: AsyncClient,
):
    tokens = await register_and_login(
        client,
        username="TokenTypeUser",
        email="token_type@example.com",
    )

    access_with_refresh = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
    )
    refresh_with_access = await client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["access_token"]},
    )

    assert access_with_refresh.status_code == 401
    assert refresh_with_access.status_code == 401


async def test_inactive_user_cannot_use_existing_access_token(
    client: AsyncClient,
    db_session,
):
    tokens = await register_and_login(
        client,
        username="InactiveTokenUser",
        email="inactive_token@example.com",
    )
    user = await db_session.scalar(
        select(User).where(User.email == "inactive_token@example.com")
    )
    user.is_active = False
    await db_session.commit()

    response = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 401


async def test_password_change_invalidates_existing_tokens(
    client: AsyncClient,
):
    tokens = await register_and_login(
        client,
        username="PasswordInvalidateUser",
        email="password_invalidate@example.com",
    )
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    password_change = await client.patch(
        "/users/me/password",
        json={
            "current_password": "password12345",
            "new_password": "new_password12345",
        },
        headers=headers,
    )
    old_access = await client.get("/users/me", headers=headers)
    old_refresh = await client.post(
        "/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )

    assert password_change.status_code == 200
    assert old_access.status_code == 401
    assert old_refresh.status_code == 401


async def test_password_change_requires_current_password(client: AsyncClient):
    tokens = await register_and_login(
        client,
        username="WrongCurrentPasswordUser",
        email="wrong_current_password@example.com",
    )
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    password_change = await client.patch(
        "/users/me/password",
        json={
            "current_password": "wrong_password",
            "new_password": "new_password12345",
        },
        headers=headers,
    )
    current_token = await client.get("/users/me", headers=headers)

    assert password_change.status_code == 400
    assert password_change.json()["detail"] == "Current password is incorrect"
    assert current_token.status_code == 200


async def test_logout_is_idempotent_and_revokes_refresh_token(
    client: AsyncClient,
):
    tokens = await register_and_login(
        client,
        username="LogoutUser",
        email="logout_user@example.com",
    )
    payload = {"refresh_token": tokens["refresh_token"]}

    first_logout = await client.post("/auth/logout", json=payload)
    second_logout = await client.post("/auth/logout", json=payload)
    refresh = await client.post("/auth/refresh", json=payload)

    assert first_logout.status_code == 204
    assert second_logout.status_code == 204
    assert refresh.status_code == 401


async def test_logout_all_revokes_every_session(
    client: AsyncClient,
    db_session,
):
    tokens = await register_and_login(
        client,
        username="LogoutAllUser",
        email="logout_all@example.com",
    )
    second_login = await client.post(
        "/auth/login",
        data={
            "username": "logout_all@example.com",
            "password": "password12345",
        },
    )
    assert second_login.status_code == 200

    response = await client.post(
        "/auth/logout-all",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    user = await db_session.scalar(
        select(User).where(User.email == "logout_all@example.com")
    )
    stored_sessions = (
        await db_session.scalars(
            select(RefreshToken).where(RefreshToken.user_id == user.id)
        )
    ).all()
    old_access = await client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert response.status_code == 204
    assert stored_sessions == []
    assert old_access.status_code == 401


async def test_only_one_concurrent_refresh_succeeds(client: AsyncClient):
    tokens = await register_and_login(
        client,
        username="ConcurrentRefreshUser",
        email="concurrent_refresh@example.com",
    )
    payload = {"refresh_token": tokens["refresh_token"]}

    responses = await asyncio.gather(
        client.post("/auth/refresh", json=payload),
        client.post("/auth/refresh", json=payload),
    )

    assert sorted(response.status_code for response in responses) == [200, 401]


async def test_login_rate_limit_returns_retry_after(
    client: AsyncClient,
    monkeypatch,
):
    async def reject_request(*args, **kwargs):
        raise RateLimitExceeded(retry_after=7)

    monkeypatch.setattr(auth_router, "enforce_rate_limit", reject_request)

    response = await client.post(
        "/auth/login",
        data={"username": "limited@example.com", "password": "password12345"},
    )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "7"
    assert response.json()["detail"] == "Too many requests"


async def test_registration_normalizes_email(client: AsyncClient):
    response = await client.post(
        "/auth/register",
        json={
            "username": "NormalizedEmailUser",
            "email": "Normalized.Email@Example.COM",
            "password": "password12345",
        },
    )

    assert response.status_code == 201
    assert response.json()["email"] == "normalized.email@example.com"


async def test_registration_rejects_overlong_password(client: AsyncClient):
    response = await client.post(
        "/auth/register",
        json={
            "username": "LongPasswordUser",
            "email": "long_password@example.com",
            "password": "a" * 129,
        },
    )

    assert response.status_code == 422
