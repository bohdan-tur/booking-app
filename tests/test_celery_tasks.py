from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.workers.tasks import (
    cleanup_old_bookings,
    generate_daily_statistics,
    process_booking_cancellation,
    process_booking_creation,
    send_daily_reminders,
    update_expired_bookings,
)

FIXED_NOW = datetime(2026, 7, 11, 12, 0, tzinfo=UTC)


@patch("app.workers.tasks.CelerySessionLocal")
@patch("app.workers.tasks.send_booking_confirmation_email")
def test_process_booking_creation_success(mock_send_email, mock_session_local):
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_booking = MagicMock(id=1, start_time=FIXED_NOW, end_time=FIXED_NOW)
    mock_user = MagicMock(email="test@example.com", username="testuser")
    mock_room = MagicMock(name="Standard Room")

    mock_result = MagicMock()
    mock_result.first.return_value = (mock_booking, mock_user, mock_room)
    mock_session.execute.return_value = mock_result
    mock_send_email.return_value = None

    result = process_booking_creation.run(1)

    assert result == {"status": "success"}
    mock_send_email.assert_called_once()


@patch("app.workers.tasks.CelerySessionLocal")
def test_process_booking_creation_not_found(mock_session_local):
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session.execute.return_value = mock_result

    result = process_booking_creation.run(999)

    assert result == {"status": "error", "message": "Booking not found"}


@patch("app.workers.tasks.CelerySessionLocal")
@patch("app.workers.tasks.send_booking_cancellation_email")
def test_process_booking_cancellation_success(mock_send_email, mock_session_local):
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_user = MagicMock(email="test@example.com", username="testuser")
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_session.execute.return_value = mock_result
    mock_send_email.return_value = None

    result = process_booking_cancellation.run(1)

    assert result == {"status": "success"}
    mock_send_email.assert_called_once()


@patch("app.workers.tasks.CelerySessionLocal")
def test_update_expired_bookings(mock_session_local):
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_result = MagicMock()
    mock_result.rowcount = 5
    mock_session.execute.return_value = mock_result

    result = update_expired_bookings.run()

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
def test_cleanup_old_bookings(mock_session_local):
    mock_session = AsyncMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_result = MagicMock()
    mock_result.rowcount = 10
    mock_session.execute.return_value = mock_result

    result = cleanup_old_bookings.run()

    assert result == 10
    mock_session.commit.assert_called_once()


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
