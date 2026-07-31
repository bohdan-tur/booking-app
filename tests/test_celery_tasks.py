import asyncio
import smtplib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from celery.exceptions import Retry
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models.booking_status import BookingStatus
from app.workers.tasks import (
    _handle_notification_failure,
    complete_finished_bookings,
    generate_daily_statistics,
    process_booking_cancellation,
    process_booking_creation,
    send_daily_reminders,
)

FIXED_NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


@patch("app.workers.tasks.send_booking_confirmation_email")
async def test_process_booking_creation_with_database(
    mock_send_email,
    engine,
    create_test_user,
    create_room,
    create_booking,
):
    user = await create_test_user(role="user")
    room = await create_room(name="Celery Confirmation Room")
    booking = await create_booking(
        user.id,
        room.id,
        FIXED_NOW,
        FIXED_NOW + timedelta(days=1),
    )
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    with patch("app.workers.tasks.CelerySessionLocal", session_factory):
        result = await asyncio.to_thread(process_booking_creation.run, booking.id)

    assert result == {"status": "success"}
    mock_send_email.assert_called_once_with(
        user_email=user.email,
        user_name=user.username,
        booking_id=booking.id,
        room_name=room.name,
        start_time=booking.start_time,
        end_time=booking.end_time,
    )


@patch("app.workers.tasks.CelerySessionLocal")
def test_process_booking_creation_not_found(mock_session_local):
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.execute.return_value = mock_result

    result = process_booking_creation.run(999)

    assert result == {"status": "error", "message": "Booking not found"}


@patch("app.workers.tasks.send_booking_cancellation_email")
async def test_process_booking_cancellation_with_database(
    mock_send_email,
    engine,
    db_session,
    create_test_user,
    create_room,
    create_booking,
):
    user = await create_test_user(role="user")
    room = await create_room(name="Celery Cancellation Room")
    booking = await create_booking(
        user.id,
        room.id,
        FIXED_NOW,
        FIXED_NOW + timedelta(days=1),
    )
    booking.status = BookingStatus.CANCELLED
    await db_session.commit()
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)

    with patch("app.workers.tasks.CelerySessionLocal", session_factory):
        result = await asyncio.to_thread(process_booking_cancellation.run, booking.id)

    assert result == {"status": "success"}
    mock_send_email.assert_called_once_with(
        user_email=user.email,
        user_name=user.username,
        booking_id=booking.id,
    )


@pytest.mark.parametrize(
    ("task", "booking_status", "expected_reason"),
    [
        (
            process_booking_creation,
            BookingStatus.CANCELLED,
            "booking_not_active",
        ),
        (
            process_booking_cancellation,
            BookingStatus.ACTIVE,
            "booking_not_cancelled",
        ),
    ],
)
async def test_notification_task_skips_incompatible_booking_status(
    task,
    booking_status,
    expected_reason,
    engine,
    db_session,
    create_test_user,
    create_room,
    create_booking,
):
    user = await create_test_user(role="user")
    room = await create_room(name=f"Skipped Notification {expected_reason}")
    booking = await create_booking(
        user.id,
        room.id,
        FIXED_NOW,
        FIXED_NOW + timedelta(days=1),
    )
    booking.status = booking_status
    await db_session.commit()

    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    with (
        patch("app.workers.tasks.CelerySessionLocal", session_factory),
        patch("app.workers.tasks.send_booking_confirmation_email") as confirmation,
        patch("app.workers.tasks.send_booking_cancellation_email") as cancellation,
    ):
        result = await asyncio.to_thread(task.run, booking.id)

    assert result == {"status": "skipped", "reason": expected_reason}
    confirmation.assert_not_called()
    cancellation.assert_not_called()


def test_transient_notification_failure_is_retried():
    task = MagicMock()
    task.name = "process_booking_creation"
    task.request.retries = 0
    retry_signal = Retry()
    task.retry.side_effect = retry_signal
    error = smtplib.SMTPServerDisconnected("Temporary SMTP failure")

    with (
        patch(
            "app.workers.tasks.get_exponential_backoff_interval",
            return_value=37,
        ),
        pytest.raises(Retry),
    ):
        _handle_notification_failure(task, error, booking_id=1)

    task.retry.assert_called_once_with(countdown=37, exc=error)


def test_permanent_notification_failure_is_not_retried():
    task = MagicMock()
    task.name = "process_booking_creation"
    error = smtplib.SMTPAuthenticationError(535, b"Authentication failed")

    with pytest.raises(smtplib.SMTPAuthenticationError):
        _handle_notification_failure(task, error, booking_id=1)

    task.retry.assert_not_called()


@patch("app.workers.tasks.CelerySessionLocal")
def test_complete_finished_bookings(mock_session_local):
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_result = MagicMock()
    mock_result.rowcount = 5
    mock_session.execute.return_value = mock_result

    result = complete_finished_bookings.run()

    assert result == 5
    mock_session.commit.assert_called_once()


@patch("app.workers.tasks.CelerySessionLocal")
@patch("app.workers.tasks.send_booking_reminder_email")
def test_send_daily_reminders(mock_send_email, mock_session_local):
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_booking = MagicMock(id=1, start_time=FIXED_NOW + timedelta(days=1))
    mock_user = MagicMock(email="test@example.com", username="testuser")
    mock_room = MagicMock(name="Standard Room")

    mock_result = MagicMock()
    mock_result.all.return_value = [(mock_booking, mock_user, mock_room)]
    mock_session.execute.return_value = mock_result
    mock_send_email.return_value = None

    result = send_daily_reminders.run()

    assert result == 1
    mock_send_email.assert_called_once()


@patch("app.workers.tasks.CelerySessionLocal")
@patch("app.workers.tasks.send_email")
def test_generate_daily_statistics(mock_send_email, mock_session_local):
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_session.scalar.side_effect = [3, 2, 4]

    mock_admins_result = MagicMock()
    mock_admins_result.scalars.return_value.all.return_value = [
        MagicMock(email="admin@example.com")
    ]
    mock_session.execute.return_value = mock_admins_result

    mock_send_email.return_value = None

    result = generate_daily_statistics.run()

    assert result["admins_notified"] == 1
    mock_send_email.assert_called_once()
