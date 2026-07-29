import smtplib
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.services.email import (
    send_booking_cancellation_email,
    send_booking_confirmation_email,
    send_booking_reminder_email,
    send_email,
)


@patch("app.services.email.smtplib.SMTP")
def test_send_email_success(mock_smtp):
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server

    send_email(
        to_email="test@example.com",
        subject="Test Subject",
        body="Test Body",
    )

    mock_smtp.assert_called_once()
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once()
    mock_server.send_message.assert_called_once()


@patch("app.services.email.smtplib.SMTP")
def test_send_email_failure(mock_smtp):
    mock_smtp.side_effect = smtplib.SMTPException("SMTP Error")

    with pytest.raises(smtplib.SMTPException):
        send_email(
            to_email="test@example.com",
            subject="Test Subject",
            body="Test Body",
        )


@patch("app.services.email.smtplib.SMTP")
def test_send_booking_confirmation_email_success(mock_smtp):
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server

    start_time = datetime(2026, 7, 12, 10, 0, tzinfo=UTC)
    end_time = datetime(2026, 7, 14, 10, 0, tzinfo=UTC)

    send_booking_confirmation_email(
        user_email="user@example.com",
        user_name="Test User",
        booking_id=1,
        room_name="Test Room",
        start_time=start_time,
        end_time=end_time,
    )

    mock_server.send_message.assert_called_once()
    sent_msg = mock_server.send_message.call_args[0][0]
    assert sent_msg["To"] == "user@example.com"
    assert sent_msg["Subject"] == "Booking Confirmation"


@patch("app.services.email.smtplib.SMTP")
def test_send_booking_cancellation_email_success(mock_smtp):
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server

    send_booking_cancellation_email(
        user_email="user@example.com",
        user_name="Test User",
        booking_id=1,
    )

    mock_server.send_message.assert_called_once()
    sent_msg = mock_server.send_message.call_args[0][0]
    assert sent_msg["To"] == "user@example.com"
    assert sent_msg["Subject"] == "Booking Cancellation"


@patch("app.services.email.smtplib.SMTP")
def test_send_booking_reminder_email_success(mock_smtp):
    mock_server = MagicMock()
    mock_smtp.return_value.__enter__.return_value = mock_server

    start_time = datetime(2026, 7, 12, 10, 0, tzinfo=UTC)

    send_booking_reminder_email(
        user_email="user@example.com",
        user_name="Test User",
        booking_id=1,
        room_name="Test Room",
        start_time=start_time,
    )

    mock_server.send_message.assert_called_once()
    sent_msg = mock_server.send_message.call_args[0][0]
    assert sent_msg["To"] == "user@example.com"
    assert sent_msg["Subject"] == "Upcoming Booking Reminder"


@patch("app.services.email.smtplib.SMTP")
def test_send_booking_confirmation_email_failure(mock_smtp):
    mock_smtp.side_effect = smtplib.SMTPException("SMTP Error")

    start_time = datetime(2026, 7, 12, 10, 0, tzinfo=UTC)
    end_time = datetime(2026, 7, 14, 10, 0, tzinfo=UTC)

    with pytest.raises(smtplib.SMTPException):
        send_booking_confirmation_email(
            user_email="user@example.com",
            user_name="Test User",
            booking_id=1,
            room_name="Test Room",
            start_time=start_time,
            end_time=end_time,
        )


@patch("app.services.email.smtplib.SMTP")
def test_send_booking_cancellation_email_failure(mock_smtp):
    mock_smtp.side_effect = OSError("Network Error")

    with pytest.raises(OSError):
        send_booking_cancellation_email(
            user_email="user@example.com",
            user_name="Test User",
            booking_id=1,
        )


@patch("app.services.email.smtplib.SMTP")
def test_send_booking_reminder_email_failure(mock_smtp):
    mock_smtp.side_effect = smtplib.SMTPException("SMTP Error")

    start_time = datetime(2026, 7, 12, 10, 0, tzinfo=UTC)

    with pytest.raises(smtplib.SMTPException):
        send_booking_reminder_email(
            user_email="user@example.com",
            user_name="Test User",
            booking_id=1,
            room_name="Test Room",
            start_time=start_time,
        )
