from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


def authorization_header(user_id: int) -> dict[str, str]:
    token = create_access_token(
        {"sub": str(user_id)},
        expires_delta=timedelta(minutes=5),
    )
    return {"Authorization": f"Bearer {token}"}


VALID_ROOM_DATA = {
    "amenities": "WiFi",
    "capacity": 2,
    "description": "Authorization test",
    "location": "Lviv",
    "name": "Protected Room",
    "price": "1000.00",
    "total_units": 1,
}


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("GET", "/users/", None),
        (
            "PATCH",
            "/users/me/password",
            {
                "current_password": "current_password123",
                "new_password": "new_password123",
            },
        ),
        ("POST", "/rooms/", VALID_ROOM_DATA),
        ("GET", "/bookings/", None),
        ("POST", "/auth/logout-all", None),
    ],
)
async def test_protected_endpoints_require_authentication(
    client: AsyncClient,
    method: str,
    path: str,
    payload: dict | None,
):
    response = await client.request(method, path, json=payload)

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("POST", "/rooms/", VALID_ROOM_DATA),
        ("DELETE", "/rooms/999999", None),
        ("PATCH", "/users/999999/role", {"role": "user"}),
        ("DELETE", "/users/999999", None),
        ("PATCH", "/users/deactivate/999999", None),
        ("PATCH", "/users/activate/999999", None),
    ],
)
async def test_manager_cannot_use_admin_only_operations(
    client: AsyncClient,
    create_test_user,
    method: str,
    path: str,
    payload: dict | None,
):
    manager = await create_test_user(role="manager")

    response = await client.request(
        method,
        path,
        json=payload,
        headers=authorization_header(manager.id),
    )

    assert response.status_code == 403


@pytest.mark.parametrize(
    "path",
    [
        "/users/",
        "/rooms/booked",
        "/bookings/",
    ],
)
async def test_user_cannot_use_manager_operations(
    client: AsyncClient,
    create_test_user,
    path: str,
):
    user = await create_test_user(role="user")

    response = await client.get(
        path,
        headers=authorization_header(user.id),
    )

    assert response.status_code == 403
