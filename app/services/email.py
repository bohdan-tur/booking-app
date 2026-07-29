import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings
from app.core.logger import logger


def send_email(to_email: str, subject: str, body: str, html_body: str | None = None) -> bool:
    try:
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = settings.EMAIL_FROM
        message["To"] = to_email

        text_part = MIMEText(body, "plain", "utf-8")
        message.attach(text_part)

        if html_body:
            html_part = MIMEText(html_body, "html", "utf-8")
            message.attach(html_part)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAIL_FROM, to_email, message.as_string())

        logger.info(f"Email successfully sent to {to_email}")
        return True

    except Exception as e:
        logger.error(f"Error sending email to {to_email}: {e}")
        return False


def send_booking_confirmation_email(
    user_email: str,
    user_name: str,
    booking_id: int,
    room_name: str,
    start_time: datetime,
    end_time: datetime,
) -> bool:
    subject = "✅ Booking Confirmation"

    body = f"""
Dear {user_name},

Thank you for your booking! 🎉

📋 Booking Details:
• Booking ID: #{booking_id}
• Room Name: {room_name}
• Check-in: {start_time.strftime("%d.%m.%Y at %H:%M")}
• Check-out: {end_time.strftime("%d.%m.%Y at %H:%M")}

Your booking is confirmed and waiting for you.

i️ Important Information:
• Check-in time: after {start_time.strftime("%H:%M")}
• Check-out time: before {end_time.strftime("%H:%M")}
• Please contact us if you have any questions.

Best regards,
Booking System Team
"""

    html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
    <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px;">
        <h2 style="color: #28a745;">✅ Booking Confirmation</h2>
        <p>Dear {user_name},</p>
        <p>Thank you for your booking! 🎉</p>

        <div style="background-color: white; padding: 15px; border-radius: 5px; margin: 20px 0;">
            <h3>📋 Booking Details:</h3>
            <ul>
                <li><strong>Booking ID:</strong> #{booking_id}</li>
                <li><strong>Room Name:</strong> {room_name}</li>
                <li><strong>Check-in:</strong> {start_time.strftime("%d.%m.%Y at %H:%M")}</li>
                <li><strong>Check-out:</strong> {end_time.strftime("%d.%m.%Y at %H:%M")}</li>
            </ul>
        </div>

        <div style="background-color: #e9ecef; padding: 15px; border-radius: 5px;">
            <h4>i️ Important Information:</h4>
            <ul>
                <li>Check-in time: after {start_time.strftime("%H:%M")}</li>
                <li>Check-out time: before {end_time.strftime("%H:%M")}</li>
                <li>Please contact us if you have any questions.</li>
            </ul>
        </div>

        <p style="margin-top: 30px;">Best regards,<br>Booking System Team</p>
    </div>
</body>
</html>
"""

    return send_email(user_email, subject, body, html_body)


def send_booking_cancellation_email(
    user_email: str, user_name: str, booking_id: int
) -> bool:
    subject = "❌ Booking Cancellation"

    body = f"""
Dear {user_name},

Your booking #{booking_id} has been cancelled.

If you did not cancel this booking, please contact us immediately.

📞 Contact Information:
• Phone: +380 XX XXX XX XX
• Email: support@booking.com

Best regards,
Booking System Team
"""

    return send_email(user_email, subject, body)


def send_booking_reminder_email(
    user_email: str,
    user_name: str,
    booking_id: int,
    room_name: str,
    start_time: datetime,
) -> bool:
    subject = "⏰ Upcoming Booking Reminder"

    body = f"""
Dear {user_name},

This is a reminder that your booking #{booking_id} starts tomorrow!

📋 Booking Details:
• Room Name: {room_name}
• Check-in: {start_time.strftime("%d.%m.%Y at %H:%M")}

Please be on time. We are looking forward to hosting you! 😊

Best regards,
Booking System Team
"""

    return send_email(user_email, subject, body)
