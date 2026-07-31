from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete

from app.core.security import create_access_token
from app.models.booking import Booking
from app.models.booking_status import BookingStatus
from app.models.room import Room


async def test_add_room_success(authenticated_client: AsyncClient):
    room_data = {
        "amenities": "WiFi, TV",
        "capacity": 2,
        "description": "Nice room",
        "location": "Lviv",
        "name": "Standard Room",
        "price": "1200.00",
        "total_units": 5,
    }
    response = await authenticated_client.post("/rooms/", json=room_data)

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Standard Room"
    assert data["price"] == "1200.00"
    assert data["total_units"] == 5
    assert "id" in data
    assert isinstance(data["id"], int)


async def test_get_rooms_catalog_success(client: AsyncClient, db_session, create_room):
    await db_session.execute(delete(Booking))
    await db_session.execute(delete(Room))
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


async def test_get_rooms_catalog_pagination(
    client: AsyncClient, db_session, create_room
):
    await db_session.execute(delete(Booking))
    await db_session.execute(delete(Room))
    await db_session.commit()

    rooms = [await create_room(name=f"Paginated Room {index}") for index in range(4)]

    response = await client.get("/rooms/all?offset=1&limit=2")

    assert response.status_code == 200
    assert [room["id"] for room in response.json()] == [rooms[1].id, rooms[2].id]


async def test_rooms_pagination_rejects_invalid_limit(client: AsyncClient):
    response = await client.get("/rooms/all?limit=0")

    assert response.status_code == 422


async def test_get_all_available_rooms_success(
    client: AsyncClient, db_session, create_room, create_test_user, create_booking
):
    await db_session.execute(delete(Booking))
    await db_session.execute(delete(Room))
    await db_session.commit()

    room_booked = await create_room(name="Booked Room", total_units=1)
    room_free = await create_room(name="Free Room", total_units=1)

    user = await create_test_user(role="user")
    now = datetime.now(UTC)

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
    await db_session.execute(delete(Booking))
    await db_session.execute(delete(Room))
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
    await db_session.execute(delete(Booking))
    await db_session.execute(delete(Room))
    await db_session.commit()

    user = await create_test_user(role="user")
    room = await create_room(name="Booked 1")
    now = datetime.now(UTC)

    await create_booking(
        user.id, room.id, now - timedelta(days=1), now + timedelta(days=1)
    )

    response = await authenticated_client.get("/rooms/booked")
    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_get_specific_booked_room_success(
    authenticated_client: AsyncClient,
    db_session,
    create_room,
    create_test_user,
    create_booking,
):
    await db_session.execute(delete(Booking))
    await db_session.execute(delete(Room))
    await db_session.commit()

    user = await create_test_user(role="user")
    room = await create_room(name="Booked 2")
    now = datetime.now(UTC)

    await create_booking(
        user.id, room.id, now - timedelta(days=1), now + timedelta(days=1)
    )

    response = await authenticated_client.get(f"/rooms/booked/{room.id}")
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
        "total_units": 3,
        "amenities": "Mini-bar",
    }

    response = await authenticated_client.patch(f"/rooms/{room.id}", json=update_data)
    assert response.status_code == 200
    assert response.json()["id"] == room.id
    assert response.json()["name"] == "Updated Room"
    assert response.json()["price"] == "1500.00"
    assert response.json()["total_units"] == 3


async def test_delete_room_success(
    authenticated_client: AsyncClient, db_session, create_room
):
    room = await create_room(name="To Delete", price=500)

    response = await authenticated_client.delete(f"/rooms/{room.id}")
    assert response.status_code == 204
    await db_session.refresh(room)
    assert room.is_active is False


async def test_get_rooms_catalog_empty(client: AsyncClient, db_session):
    await db_session.execute(delete(Booking))
    await db_session.execute(delete(Room))
    await db_session.commit()

    response = await client.get("/rooms/all")
    assert response.status_code == 200
    assert response.json() == []


async def test_get_all_available_rooms_empty(client: AsyncClient, db_session):
    await db_session.execute(delete(Booking))
    await db_session.execute(delete(Room))
    await db_session.commit()

    response = await client.get("/rooms/available")
    assert response.status_code == 200
    assert response.json() == []


async def test_get_specific_available_room_not_found(client: AsyncClient):
    response = await client.get("/rooms/999999/available")
    assert response.status_code == 404


async def test_get_all_booked_rooms_empty(
    authenticated_client: AsyncClient, db_session
):
    await db_session.execute(delete(Booking))
    await db_session.commit()

    response = await authenticated_client.get("/rooms/booked")
    assert response.status_code == 200
    assert response.json() == []


async def test_get_specific_booked_room_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/rooms/booked/999999")
    assert response.status_code == 404


async def test_update_room_not_found(authenticated_client: AsyncClient):
    update_data = {
        "price": 1500,
        "name": "Ghost Room",
        "capacity": 2,
        "location": "Odessa",
        "total_units": 3,
        "amenities": "Mini-bar",
    }
    response = await authenticated_client.patch("/rooms/999999", json=update_data)
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
                "total_units": 1,
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
                "total_units": 1,
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
                "total_units": -5,
                "amenities": "WiFi",
                "description": "Nice room",
            },
            "total_units",
        ),
        (
            {
                "price": 500,
                "name": "",
                "capacity": 2,
                "location": "Valid Location",
                "total_units": 1,
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
                "total_units": 1,
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
                "total_units": 1,
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
        "total_units": 1,
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
        "total_units": 3,
        "amenities": "Mini-bar",
    }

    response = await client.patch(
        f"/rooms/{room.id}",
        json=update_data,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


async def test_room_inventory_cannot_decrease_with_active_bookings(
    authenticated_client: AsyncClient,
    db_session,
    create_room,
    create_test_user,
    create_booking,
):
    user = await create_test_user(role="user")
    room = await create_room(name="Capacity Guard", total_units=3)
    start = datetime.now(UTC) + timedelta(days=10)
    await create_booking(user.id, room.id, start, start + timedelta(days=2))
    await create_booking(user.id, room.id, start, start + timedelta(days=2))

    response = await authenticated_client.patch(
        f"/rooms/{room.id}", json={"total_units": 1}
    )

    assert response.status_code == 409
    await db_session.refresh(room)
    assert room.total_units == 3


async def test_cancelled_booking_does_not_prevent_inventory_decrease(
    authenticated_client: AsyncClient,
    db_session,
    create_room,
    create_test_user,
    create_booking,
):
    user = await create_test_user(role="user")
    room = await create_room(name="Cancelled Capacity", total_units=2)
    start = datetime.now(UTC) + timedelta(days=10)
    booking = await create_booking(user.id, room.id, start, start + timedelta(days=2))
    booking.status = BookingStatus.CANCELLED
    await db_session.commit()

    response = await authenticated_client.patch(
        f"/rooms/{room.id}", json={"total_units": 0}
    )

    assert response.status_code == 200
    await db_session.refresh(room)
    assert room.total_units == 0


async def test_archiving_room_preserves_booking_history(
    authenticated_client: AsyncClient,
    db_session,
    create_room,
    create_test_user,
    create_booking,
):
    user = await create_test_user(role="user")
    room = await create_room(name="Archived History")
    start = datetime.now(UTC) + timedelta(days=10)
    booking = await create_booking(user.id, room.id, start, start + timedelta(days=2))

    response = await authenticated_client.delete(f"/rooms/{room.id}")

    assert response.status_code == 204
    await db_session.refresh(booking)
    assert booking.room_id == room.id


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
