from httpx import AsyncClient


async def test_register_user_success(client: AsyncClient):
    payload = {
        "username": "BohdanSuccess",
        "email": "bohdan_success@example.com",
        "password": "password12345"
    }
    response = await client.post("/auth/register", json=payload)

    assert response.status_code == 201
    assert response.json()["email"] == payload["email"]


async def test_login_user_by_email(client: AsyncClient):
    payload = {
        "username": "LoginEmailUser",
        "email": "login_email@example.com",
        "password": "password12345"
    }
    await client.post("/auth/register", json=payload)

    login_data = {
        "username": payload["email"],
        "password": payload["password"]
    }
    response = await client.post("/auth/login", data=login_data)

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


async def test_login_user_by_username(client: AsyncClient):
    payload = {
        "username": "LoginUsernameUser",
        "email": "login_username@example.com",
        "password": "password12345"
    }
    await client.post("/auth/register", json=payload)

    login_data = {
        "username": payload["username"],
        "password": payload["password"]
    }
    response = await client.post("/auth/login", data=login_data)

    assert response.status_code == 200
    assert "access_token" in response.json()


async def test_refresh_token_success(client: AsyncClient):
    payload = {
        "username": "RefreshUser",
        "email": "refresh@example.com",
        "password": "password12345"
    }
    await client.post("/auth/register", json=payload)

    login_data = {
        "username": payload["email"],
        "password": payload["password"]
    }
    login_response = await client.post("/auth/login", data=login_data)
    refresh_token = login_response.json()["refresh_token"]

    refresh_payload = {
        "refresh_token": refresh_token
    }

    response = await client.post("/auth/", json=refresh_payload)

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()


async def test_login_wrong_password(client: AsyncClient):
    payload = {
        "username": "WrongPassUser",
        "email": "wrong_pass@example.com",
        "password": "CorrectPassword123"
    }
    await client.post("/auth/register", json=payload)

    login_data = {
        "username": payload["email"],
        "password": "WrongPassword123"
    }
    response = await client.post("/auth/login", data=login_data)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_login_nonexistent_user(client: AsyncClient):
    login_data = {
        "username": "nobody_exists@example.com",
        "password": "SomePassword123"
    }
    response = await client.post("/auth/login", data=login_data)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_register_duplicate_user(client: AsyncClient):
    payload = {
        "username": "DuplicateUser",
        "email": "duplicate@example.com",
        "password": "password12345"
    }

    response1 = await client.post("/auth/register", json=payload)
    assert response1.status_code == 201

    response2 = await client.post("/auth/register", json=payload)
    assert response2.status_code == 400
    assert response2.json()["detail"] == "User with this email already exists"


async def test_refresh_token_invalid(client: AsyncClient):
    refresh_payload = {
        "refresh_token": "fake.invalid.token"
    }

    response = await client.post("/auth/", json=refresh_payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate refresh token"