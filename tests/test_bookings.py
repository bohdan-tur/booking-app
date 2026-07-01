import pytest
from datetime import datetime, timedelta, UTC
from httpx import AsyncClient
from sqlalchemy import delete

from app.models.room_model import Rooms
from app.models.booking_model import Bookings
from app.core.security import create_access_token


async def test_book_room_success(authenticated_client: AsyncClient, db_session, create_room):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    room = await create_room(name="Book Room", quantity=2)
    start = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1)
    end = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=3)

    params = {
        "room_id_to_book": room.id,
        "start_time": start.isoformat(),
        "end_time": end.isoformat()
    }

    response = await authenticated_client.post("/bookings/", params=params)

    assert response.status_code == 201
    data = response.json()
    assert data["room_id"] == room.id
    assert "id" in data


async def test_get_all_bookings_success(authenticated_client: AsyncClient, db_session, create_room, create_test_user,
                                        create_booking):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    user = await create_test_user(role="user")
    room = await create_room()
    now = datetime.now(UTC).replace(tzinfo=None)
    await create_booking(user.id, room.id, now, now + timedelta(days=1))

    response = await authenticated_client.get("/bookings/")

    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert response.json()[0]["room_id"] == room.id


async def test_get_own_booking_success(client: AsyncClient, db_session, create_room, create_test_user, create_booking):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    user = await create_test_user(role="user")
    room = await create_room()
    now = datetime.now(UTC).replace(tzinfo=None)
    booking = await create_booking(user.id, room.id, now, now + timedelta(days=1))

    user_token = create_access_token(
        data={"sub": str(user.id), "role": "user"},
        expires_delta=timedelta(minutes=5)
    )

    response = await client.get(
        f"/bookings/{booking.id}",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    assert response.json()["id"] == booking.id


async def test_update_booking_success(authenticated_client: AsyncClient, db_session, create_room, create_test_user,
                                      create_booking):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    user = await create_test_user(role="user")
    room = await create_room()
    now = datetime.now(UTC).replace(tzinfo=None)
    booking = await create_booking(user.id, room.id, now, now + timedelta(days=1))

    update_data = {
        "start_time": (now + timedelta(days=5)).isoformat(),
        "end_time": (now + timedelta(days=7)).isoformat()
    }

    response = await authenticated_client.patch(f"/bookings/{booking.id}", json=update_data)

    assert response.status_code == 200
    assert response.json() == {"status": "success"}


async def test_cancel_own_booking_success(client: AsyncClient, db_session, create_room, create_test_user,
                                          create_booking):
    await db_session.execute(delete(Bookings))
    await db_session.execute(delete(Rooms))
    await db_session.commit()

    user = await create_test_user(role="user")
    room = await create_room()
    now = datetime.now(UTC).replace(tzinfo=None)
    booking = await create_booking(user.id, room.id, now, now + timedelta(days=1))

    user_token = create_access_token(
        data={"sub": str(user.id), "role": "user"},
        expires_delta=timedelta(minutes=5)
    )

    response = await client.delete(
        f"/bookings/{booking.id}",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 204