import uuid
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
        "quantity": 5
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


async def test_get_all_available_rooms_success(client: AsyncClient, db_session, create_room, create_test_user,
                                               create_booking):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    room_booked = await create_room(name="Booked Room", quantity=1)
    room_free = await create_room(name="Free Room", quantity=1)

    user = await create_test_user(role="user")
    now = datetime.now(UTC).replace(tzinfo=None)

    await create_booking(user.id, room_booked.id, now - timedelta(days=1), now + timedelta(days=1))

    response = await client.get("/rooms/available")
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "Free Room"
    assert data[0]["id"] == room_free.id


async def test_get_specific_available_room_success(client: AsyncClient, db_session, create_room):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    room = await create_room(name="Specific Avail", price=1200)

    response = await client.get(f"/rooms/{room.id}/available")
    assert response.status_code == 200
    assert response.json()["id"] == room.id


async def test_get_all_booked_rooms_success(authenticated_client: AsyncClient, db_session, create_room,
                                            create_test_user, create_booking):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    user = await create_test_user(role="user")
    room = await create_room(name="Booked 1")
    now = datetime.now(UTC).replace(tzinfo=None)

    await create_booking(user.id, room.id, now - timedelta(days=1), now + timedelta(days=1))

    response = await authenticated_client.get("/rooms/")
    assert response.status_code == 200
    assert len(response.json()) >= 1


async def test_get_specific_booked_room_success(authenticated_client: AsyncClient, db_session, create_room,
                                                create_test_user, create_booking):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    user = await create_test_user(role="user")
    room = await create_room(name="Booked 2")
    now = datetime.now(UTC).replace(tzinfo=None)

    await create_booking(user.id, room.id, now - timedelta(days=1), now + timedelta(days=1))

    response = await authenticated_client.get(f"/rooms/{room.id}")
    assert response.status_code == 200
    assert response.json()["id"] == room.id


async def test_update_room_success(authenticated_client: AsyncClient, db_session, create_room):
    room = await create_room(name="To Update", price=1000)

    update_data = {
        "price": 1500,
        "name": "Updated Room",
        "capacity": 2,
        "location": "Odessa",
        "quantity": 3,
        "amenities": "Mini-bar"
    }

    response = await authenticated_client.put(f"/rooms/{room.id}", json=update_data)
    assert response.status_code == 200


async def test_delete_room_success(authenticated_client: AsyncClient, db_session, create_room):
    room = await create_room(name="To Delete", price=500)

    response = await authenticated_client.delete(f"/rooms/{room.id}")
    assert response.status_code == 204