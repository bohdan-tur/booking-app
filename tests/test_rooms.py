import pytest
from datetime import datetime, timedelta, UTC
from httpx import AsyncClient
from sqlalchemy import delete

from app.models.room_model import Rooms
from app.models.booking_model import Bookings
from app.core.security import create_access_token


async def test_add_room_success(authenticated_client: AsyncClient):
    room_data = {
        "amenities": "WiFi, TV",
        "capacity": 2,
        "description": "Nice room",
        "location": "Lviv",
        "name": "Standard Room",
        "price": 1200,
        "quantity": 5,
    }
    response = await authenticated_client.post("/rooms/", json=room_data)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Standard Room"
    assert data["price"] == 1200
    assert data["quantity"] == 5
    assert "id" in data
    assert isinstance(data["id"], int)


async def test_get_rooms_catalog_success(client: AsyncClient, db_session, create_room):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    await create_room(name="Kyiv Room", location="Kyiv", price=2500)
    await create_room(name="Lviv Room", location="Lviv", price=1500)

    response = await client.get("/rooms/all")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    names = [room["name"] for room in data]
    assert "Kyiv Room" in names
    assert "Lviv Room" in names


async def test_get_all_available_rooms_success(
    client: AsyncClient, db_session, create_room, create_test_user, create_booking
):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    room_booked = await create_room(name="Booked Room", quantity=1)
    room_free = await create_room(name="Free Room", quantity=1)

    user = await create_test_user(role="user")
    now = datetime.now(UTC).replace(tzinfo=None)

    await create_booking(
        user.id, room_booked.id, now - timedelta(days=1), now + timedelta(days=1)
    )

    response = await client.get("/rooms/available")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Free Room"
    assert data[0]["id"] == room_free.id


async def test_get_specific_available_room_success(
    client: AsyncClient, db_session, create_room
):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    room = await create_room(name="Specific Avail", price=1200)

    response = await client.get(f"/rooms/{room.id}/available")
    assert response.status_code == 200
    assert response.json()["id"] == room.id


async def test_get_all_booked_rooms_success(
    authenticated_client: AsyncClient,
    db_session,
    create_room,
    create_test_user,
    create_booking,
):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    user = await create_test_user(role="user")
    room = await create_room(name="Booked 1")
    now = datetime.now(UTC).replace(tzinfo=None)

    await create_booking(
        user.id, room.id, now - timedelta(days=1), now + timedelta(days=1)
    )

    response = await authenticated_client.get("/rooms/")
    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_get_specific_booked_room_success(
    authenticated_client: AsyncClient,
    db_session,
    create_room,
    create_test_user,
    create_booking,
):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    user = await create_test_user(role="user")
    room = await create_room(name="Booked 2")
    now = datetime.now(UTC).replace(tzinfo=None)

    await create_booking(
        user.id, room.id, now - timedelta(days=1), now + timedelta(days=1)
    )

    response = await authenticated_client.get(f"/rooms/{room.id}")
    assert response.status_code == 200
    assert response.json()["id"] == room.id


async def test_update_room_success(
    authenticated_client: AsyncClient, db_session, create_room
):
    room = await create_room(name="To Update", price=1000)

    update_data = {
        "price": 1500,
        "name": "Updated Room",
        "capacity": 2,
        "location": "Odessa",
        "quantity": 3,
        "amenities": "Mini-bar",
    }

    response = await authenticated_client.put(f"/rooms/{room.id}", json=update_data)
    assert response.status_code == 200


async def test_delete_room_success(
    authenticated_client: AsyncClient, db_session, create_room
):
    room = await create_room(name="To Delete", price=500)

    response = await authenticated_client.delete(f"/rooms/{room.id}")
    assert response.status_code == 204


async def test_get_rooms_catalog_not_found(client: AsyncClient, db_session):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    response = await client.get("/rooms/all")
    assert response.status_code == 404


async def test_get_all_available_rooms_not_found(client: AsyncClient, db_session):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    response = await client.get("/rooms/available")
    assert response.status_code == 404


async def test_get_specific_available_room_not_found(client: AsyncClient):
    response = await client.get("/rooms/999999/available")
    assert response.status_code == 404


async def test_get_all_booked_rooms_not_found(
    authenticated_client: AsyncClient, db_session
):
    await db_session.execute(delete(Bookings))
    await db_session.commit()

    response = await authenticated_client.get("/rooms/")
    assert response.status_code == 404


async def test_get_specific_booked_room_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/rooms/999999")
    assert response.status_code == 404


async def test_update_room_not_found(authenticated_client: AsyncClient):
    update_data = {
        "price": 1500,
        "name": "Ghost Room",
        "capacity": 2,
        "location": "Odessa",
        "quantity": 3,
        "amenities": "Mini-bar",
    }
    response = await authenticated_client.put("/rooms/999999", json=update_data)
    assert response.status_code == 404


async def test_delete_room_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.delete("/rooms/999999")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "invalid_data, expected_error_field",
    [
        (
            {
                "price": -500,
                "name": "Valid Room Name",
                "capacity": 2,
                "location": "Valid Location",
                "quantity": 1,
                "amenities": "WiFi",
                "description": "Nice room",
            },
            "price",
        ),
        (
            {
                "price": 500,
                "name": "Valid Room Name",
                "capacity": 0,
                "location": "Valid Location",
                "quantity": 1,
                "amenities": "WiFi",
                "description": "Nice room",
            },
            "capacity",
        ),
        (
            {
                "price": 500,
                "name": "Valid Room Name",
                "capacity": 2,
                "location": "Valid Location",
                "quantity": -5,
                "amenities": "WiFi",
                "description": "Nice room",
            },
            "quantity",
        ),
        (
            {
                "price": 500,
                "name": "",
                "capacity": 2,
                "location": "Valid Location",
                "quantity": 1,
                "amenities": "WiFi",
                "description": "Nice room",
            },
            "name",
        ),
        (
            {
                "price": "totally free",
                "name": "Valid Room Name",
                "capacity": 2,
                "location": "Valid Location",
                "quantity": 1,
                "amenities": "WiFi",
                "description": "Nice room",
            },
            "price",
        ),
        (
            {
                "price": 500,
                "name": "Valid Room Name",
                "capacity": 2,
                "quantity": 1,
                "amenities": "WiFi",
                "description": "Nice room",
            },
            "location",
        ),
    ],
)
async def test_create_room_validation_errors(
    authenticated_client: AsyncClient, invalid_data, expected_error_field
):
    response = await authenticated_client.post("/rooms/", json=invalid_data)

    assert response.status_code == 422

    errors = response.json()["detail"]
    error_fields = [err["loc"][-1] for err in errors]

    assert expected_error_field in error_fields


async def test_add_room_forbidden(client: AsyncClient, create_test_user):
    user = await create_test_user(role="user")
    user_token = create_access_token(
        data={"sub": str(user.id), "role": "user"}, expires_delta=timedelta(minutes=5)
    )

    room_data = {
        "amenities": "WiFi",
        "capacity": 2,
        "description": "Test",
        "location": "Lviv",
        "name": "New Room",
        "price": 1000,
        "quantity": 1,
    }

    response = await client.post(
        "/rooms/", json=room_data, headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403


async def test_update_room_forbidden(
    client: AsyncClient, create_test_user, create_room
):
    user = await create_test_user(role="user")
    room = await create_room(name="To Update Forbidden")

    user_token = create_access_token(
        data={"sub": str(user.id), "role": "user"}, expires_delta=timedelta(minutes=5)
    )

    update_data = {
        "price": 1500,
        "name": "Hacked Room",
        "capacity": 2,
        "location": "Odessa",
        "quantity": 3,
        "amenities": "Mini-bar",
    }

    response = await client.put(
        f"/rooms/{room.id}",
        json=update_data,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


async def test_delete_room_forbidden(
    client: AsyncClient, create_test_user, create_room
):
    user = await create_test_user(role="user")
    room = await create_room(name="To Delete Forbidden")

    user_token = create_access_token(
        data={"sub": str(user.id), "role": "user"}, expires_delta=timedelta(minutes=5)
    )

    response = await client.delete(
        f"/rooms/{room.id}", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403
