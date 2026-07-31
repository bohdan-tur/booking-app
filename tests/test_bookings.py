import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select

from app.core.security import create_access_token
from app.models.booking import Booking
from app.models.booking_status import BookingStatus
from app.models.room import Room


@patch("app.api.routers.bookings.process_booking_creation.delay")
async def test_book_room_success(
    mock_delay, authenticated_client: AsyncClient, db_session, create_room
):
    await db_session.execute(delete(Booking))
    await db_session.execute(delete(Room))
    await db_session.commit()

    room = await create_room(name="Book Room", total_units=2)
    start = datetime.now(UTC) + timedelta(days=1)
    end = datetime.now(UTC) + timedelta(days=3)

    params = {
        "room_id": room.id,
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
    }

    response = await authenticated_client.post("/bookings/", json=params)

    assert response.status_code == 201
    data = response.json()
    assert data["room_id"] == room.id
    assert "id" in data

    mock_delay.assert_called_once()


async def test_get_all_bookings_success(
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
    room = await create_room()
    now = datetime.now(UTC)
    await create_booking(user.id, room.id, now, now + timedelta(days=1))

    response = await authenticated_client.get("/bookings/")

    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert response.json()[0]["room_id"] == room.id


async def test_get_own_booking_success(
    client: AsyncClient, db_session, create_room, create_test_user, create_booking
):
    await db_session.execute(delete(Booking))
    await db_session.execute(delete(Room))
    await db_session.commit()

    user = await create_test_user(role="user")
    room = await create_room()
    now = datetime.now(UTC)
    booking = await create_booking(user.id, room.id, now, now + timedelta(days=1))

    user_token = create_access_token(
        data={"sub": str(user.id), "role": "user"}, expires_delta=timedelta(minutes=5)
    )

    response = await client.get(
        f"/bookings/{booking.id}", headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 200
    assert response.json()["id"] == booking.id


async def test_update_booking_success(
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
    room = await create_room()
    now = datetime.now(UTC)
    booking = await create_booking(user.id, room.id, now, now + timedelta(days=1))

    update_data = {
        "start_time": (now + timedelta(days=5)).isoformat(),
        "end_time": (now + timedelta(days=7)).isoformat(),
    }

    response = await authenticated_client.patch(
        f"/bookings/{booking.id}", json=update_data
    )

    assert response.status_code == 200
    assert response.json() == {"status": "success"}


@patch("app.api.routers.bookings.process_booking_cancellation.delay")
async def test_cancel_own_booking_success(
    mock_delay,
    client: AsyncClient,
    db_session,
    create_room,
    create_test_user,
    create_booking,
):
    await db_session.execute(delete(Booking))
    await db_session.execute(delete(Room))
    await db_session.commit()

    user = await create_test_user(role="user")
    room = await create_room()
    now = datetime.now(UTC)
    booking = await create_booking(user.id, room.id, now, now + timedelta(days=1))

    user_token = create_access_token(
        data={"sub": str(user.id), "role": "user"}, expires_delta=timedelta(minutes=5)
    )

    response = await client.delete(
        f"/bookings/{booking.id}", headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 204

    mock_delay.assert_called_once()
    await db_session.refresh(booking)
    assert booking.status == BookingStatus.CANCELLED


async def test_get_all_bookings_not_found(
    authenticated_client: AsyncClient, db_session
):
    await db_session.execute(delete(Booking))
    await db_session.commit()

    response = await authenticated_client.get("/bookings/")
    assert response.status_code == 404


async def test_get_single_booking_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/bookings/999999")
    assert response.status_code == 404


async def test_update_booking_not_found(authenticated_client: AsyncClient):
    now = datetime.now(UTC)
    update_data = {
        "start_time": (now + timedelta(days=5)).isoformat(),
        "end_time": (now + timedelta(days=7)).isoformat(),
    }
    response = await authenticated_client.patch("/bookings/999999", json=update_data)
    assert response.status_code == 404


async def test_cancel_booking_not_found(authenticated_client: AsyncClient):
    response = await authenticated_client.delete("/bookings/999999")
    assert response.status_code == 404


async def test_get_all_bookings_forbidden(client: AsyncClient, create_test_user):
    user = await create_test_user(role="user")
    user_token = create_access_token(
        data={"sub": str(user.id), "role": "user"}, expires_delta=timedelta(minutes=5)
    )

    response = await client.get(
        "/bookings/", headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403


async def test_get_others_booking_forbidden(
    client: AsyncClient, db_session, create_room, create_test_user, create_booking
):
    user_owner = await create_test_user(role="user")
    user_thief = await create_test_user(role="user")
    room = await create_room()
    now = datetime.now(UTC)
    booking = await create_booking(user_owner.id, room.id, now, now + timedelta(days=1))

    thief_token = create_access_token(
        data={"sub": str(user_thief.id), "role": "user"},
        expires_delta=timedelta(minutes=5),
    )

    response = await client.get(
        f"/bookings/{booking.id}", headers={"Authorization": f"Bearer {thief_token}"}
    )
    assert response.status_code == 403


async def test_update_booking_forbidden(
    client: AsyncClient, db_session, create_room, create_test_user, create_booking
):
    user = await create_test_user(role="user")
    room = await create_room()
    now = datetime.now(UTC)
    booking = await create_booking(user.id, room.id, now, now + timedelta(days=1))

    user_token = create_access_token(
        data={"sub": str(user.id), "role": "user"}, expires_delta=timedelta(minutes=5)
    )

    update_data = {
        "start_time": (now + timedelta(days=5)).isoformat(),
        "end_time": (now + timedelta(days=7)).isoformat(),
    }

    response = await client.patch(
        f"/bookings/{booking.id}",
        json=update_data,
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert response.status_code == 403


async def test_cancel_others_booking_forbidden(
    client: AsyncClient, db_session, create_room, create_test_user, create_booking
):
    user_owner = await create_test_user(role="user")
    user_thief = await create_test_user(role="user")
    room = await create_room()
    now = datetime.now(UTC)
    booking = await create_booking(user_owner.id, room.id, now, now + timedelta(days=1))

    thief_token = create_access_token(
        data={"sub": str(user_thief.id), "role": "user"},
        expires_delta=timedelta(minutes=5),
    )

    response = await client.delete(
        f"/bookings/{booking.id}", headers={"Authorization": f"Bearer {thief_token}"}
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "invalid_params, expected_error_field",
    [
        (
            {"start_time": "2024-10-10T10:00:00", "end_time": "2024-10-12T10:00:00"},
            "room_id",
        ),
        ({"room_id": 1, "end_time": "2024-10-12T10:00:00"}, "start_time"),
        (
            {
                "room_id": 1,
                "start_time": "not-a-date",
                "end_time": "2024-10-12T10:00:00",
            },
            "start_time",
        ),
    ],
)
async def test_book_room_validation_errors(
    authenticated_client: AsyncClient, invalid_params, expected_error_field
):
    response = await authenticated_client.post("/bookings/", json=invalid_params)
    assert response.status_code == 422

    errors = response.json()["detail"]
    error_fields = [err["loc"][-1] for err in errors]
    assert expected_error_field in error_fields


async def test_book_room_rejects_naive_datetime(
    authenticated_client: AsyncClient, create_room
):
    room = await create_room(name="Timezone Room")
    response = await authenticated_client.post(
        "/bookings/",
        json={
            "room_id": room.id,
            "start_time": "2026-08-15T14:00:00",
            "end_time": "2026-08-16T11:00:00",
        },
    )

    assert response.status_code == 422


async def test_update_booking_rejects_overlapping_period(
    authenticated_client: AsyncClient,
    create_room,
    create_test_user,
    create_booking,
):
    user = await create_test_user(role="user")
    room = await create_room(name="Update Conflict", total_units=1)
    start = datetime.now(UTC) + timedelta(days=10)
    blocking_booking = await create_booking(
        user.id, room.id, start, start + timedelta(days=2)
    )
    booking_to_update = await create_booking(
        user.id,
        room.id,
        start + timedelta(days=4),
        start + timedelta(days=6),
    )

    response = await authenticated_client.patch(
        f"/bookings/{booking_to_update.id}",
        json={
            "start_time": blocking_booking.start_time.isoformat(),
            "end_time": blocking_booking.end_time.isoformat(),
        },
    )

    assert response.status_code == 409


async def test_cancelled_booking_does_not_block_availability(
    authenticated_client: AsyncClient,
    db_session,
    create_room,
    create_test_user,
    create_booking,
):
    user = await create_test_user(role="user")
    room = await create_room(name="Cancelled Availability", total_units=1)
    start = datetime.now(UTC) + timedelta(days=10)
    booking = await create_booking(user.id, room.id, start, start + timedelta(days=2))
    booking.status = BookingStatus.CANCELLED
    await db_session.commit()

    with patch("app.api.routers.bookings.process_booking_creation.delay"):
        response = await authenticated_client.post(
            "/bookings/",
            json={
                "room_id": room.id,
                "start_time": start.isoformat(),
                "end_time": (start + timedelta(days=2)).isoformat(),
            },
        )

    assert response.status_code == 201


async def test_completed_booking_cannot_be_updated(
    authenticated_client: AsyncClient,
    db_session,
    create_room,
    create_test_user,
    create_booking,
):
    user = await create_test_user(role="user")
    room = await create_room(name="Completed Booking")
    start = datetime.now(UTC) + timedelta(days=10)
    booking = await create_booking(user.id, room.id, start, start + timedelta(days=2))
    booking.status = BookingStatus.COMPLETED
    await db_session.commit()

    response = await authenticated_client.patch(
        f"/bookings/{booking.id}",
        json={
            "start_time": (start + timedelta(days=3)).isoformat(),
            "end_time": (start + timedelta(days=4)).isoformat(),
        },
    )

    assert response.status_code == 409


@patch("app.api.routers.bookings.process_booking_creation.delay")
async def test_concurrent_booking_requests_respect_room_inventory(
    mock_delay,
    authenticated_client: AsyncClient,
    db_session,
    create_room,
):
    room = await create_room(name="Concurrency Room", total_units=1)
    start = datetime.now(UTC) + timedelta(days=10)
    payload = {
        "room_id": room.id,
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(days=2)).isoformat(),
    }

    responses = await asyncio.gather(
        *(authenticated_client.post("/bookings/", json=payload) for _ in range(10))
    )

    status_codes = [response.status_code for response in responses]
    assert status_codes.count(201) == 1
    assert status_codes.count(409) == 9
    booking_count = await db_session.scalar(
        select(func.count(Booking.id)).where(
            Booking.room_id == room.id,
            Booking.status == BookingStatus.ACTIVE,
        )
    )
    assert booking_count == 1
    mock_delay.assert_called_once()
