from datetime import datetime
from unittest.mock import patch, MagicMock
from app.services.email import (
    send_email,
    send_booking_confirmation_email,
    send_booking_cancellation_email,
    send_booking_reminder_email,
)


def test_send_email_success():
    with patch("app.services.email.smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        result = send_email("test@example.com", "Test Subject", "Test Body")

        assert result is True
        mock_smtp.assert_called_once()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.sendmail.assert_called_once()


def test_send_email_with_html():
    with patch("app.services.email.smtplib.SMTP") as mock_smtp:
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        result = send_email(
            "test@example.com",
            "Test Subject",
            "Test Body",
            "<html><body>HTML Body</body></html>",
        )

        assert result is True
        mock_server.sendmail.assert_called_once()


def test_send_email_failure():
    with patch("app.services.email.smtplib.SMTP") as mock_smtp:
        mock_smtp.side_effect = Exception("SMTP Error")

        result = send_email("test@example.com", "Test Subject", "Test Body")

        assert result is False


def test_send_booking_confirmation_email():
    with patch("app.services.email.send_email") as mock_send_email:
        mock_send_email.return_value = True

        start_time = datetime(2026, 7, 12, 10, 0)
        end_time = datetime(2026, 7, 14, 10, 0)

        result = send_booking_confirmation_email(
            user_email="user@example.com",
            user_name="Test User",
            booking_id=1,
            room_name="Test Room",
            start_time=start_time,
            end_time=end_time,
        )

        assert result is True
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert call_args[0][0] == "user@example.com"
        assert "✅ Booking Confirmation" in call_args[0][1]
        assert "Test User" in call_args[0][2]
        assert "#1" in call_args[0][2]
        assert "Test Room" in call_args[0][2]


def test_send_booking_cancellation_email():
    with patch("app.services.email.send_email") as mock_send_email:
        mock_send_email.return_value = True

        result = send_booking_cancellation_email(
            user_email="user@example.com",
            user_name="Test User",
            booking_id=1,
        )

        assert result is True
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert call_args[0][0] == "user@example.com"
        assert "❌ Booking Cancellation" in call_args[0][1]
        assert "#1" in call_args[0][2]


def test_send_booking_reminder_email():
    with patch("app.services.email.send_email") as mock_send_email:
        mock_send_email.return_value = True

        start_time = datetime(2026, 7, 12, 10, 0)

        result = send_booking_reminder_email(
            user_email="user@example.com",
            user_name="Test User",
            booking_id=1,
            room_name="Test Room",
            start_time=start_time,
        )

        assert result is True
        mock_send_email.assert_called_once()
        call_args = mock_send_email.call_args
        assert call_args[0][0] == "user@example.com"
        assert "⏰ Upcoming Booking Reminder" in call_args[0][1]
        assert "#1" in call_args[0][2]
        assert "Test Room" in call_args[0][2]


def test_send_booking_confirmation_email_failure():
    with patch("app.services.email.send_email") as mock_send_email:
        mock_send_email.return_value = False

        start_time = datetime(2026, 7, 12, 10, 0)
        end_time = datetime(2026, 7, 14, 10, 0)

        result = send_booking_confirmation_email(
            user_email="user@example.com",
            user_name="Test User",
            booking_id=1,
            room_name="Test Room",
            start_time=start_time,
            end_time=end_time,
        )

        assert result is False


def test_send_booking_cancellation_email_failure():
    with patch("app.services.email.send_email") as mock_send_email:
        mock_send_email.return_value = False

        result = send_booking_cancellation_email(
            user_email="user@example.com",
            user_name="Test User",
            booking_id=1,
        )

        assert result is False


def test_send_booking_reminder_email_failure():
    with patch("app.services.email.send_email") as mock_send_email:
        mock_send_email.return_value = False

        start_time = datetime(2026, 7, 12, 10, 0)

        result = send_booking_reminder_email(
            user_email="user@example.com",
            user_name="Test User",
            booking_id=1,
            room_name="Test Room",
            start_time=start_time,
        )

        assert result is False
