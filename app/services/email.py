import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import settings
from app.core.logger import logger

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "templates" / "emails"

LOCAL_TZ = ZoneInfo(settings.TIMEZONE)


def format_datetime_local(
    dt: datetime,
    fmt: str = "%d.%m.%Y at %H:%M",
) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    return dt.astimezone(LOCAL_TZ).strftime(fmt)


template_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(("html", "xml")),
)

template_env.filters["local_time"] = format_datetime_local


def _build_message(
    *,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> EmailMessage:
    message = EmailMessage()

    message["Subject"] = subject
    message["From"] = settings.EMAIL_FROM
    message["To"] = to_email
    message["Date"] = formatdate(localtime=True)
    message["Message-ID"] = make_msgid()

    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    return message


def _send_message(message: EmailMessage) -> None:
    context = ssl.create_default_context()

    try:
        with smtplib.SMTP(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT,
        ) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()

            server.login(
                settings.SMTP_USER,
                settings.SMTP_PASSWORD,
            )

            server.send_message(message)

        logger.info("Email sent successfully")

    except (smtplib.SMTPException, OSError) as exc:
        logger.error(
            "Failed to send email: error=%s",
            type(exc).__name__,
        )
        raise


def _render_and_send(
    *,
    template_name: str,
    to_email: str,
    subject: str,
    context: dict,
) -> None:
    render_context = {
        **context,
        "support_email": settings.SUPPORT_EMAIL,
        "support_phone": settings.SUPPORT_PHONE,
    }

    text_body = template_env.get_template(f"{template_name}.txt").render(
        **render_context
    )

    html_body = template_env.get_template(f"{template_name}.html").render(
        **render_context
    )

    message = _build_message(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )

    _send_message(message)


def send_booking_confirmation_email(
    *,
    user_email: str,
    user_name: str,
    booking_id: int,
    room_name: str,
    start_time: datetime,
    end_time: datetime,
) -> None:
    _render_and_send(
        template_name="confirmation",
        to_email=user_email,
        subject="Booking Confirmation",
        context={
            "user_name": user_name,
            "booking_id": booking_id,
            "room_name": room_name,
            "start_time": start_time,
            "end_time": end_time,
        },
    )


def send_booking_cancellation_email(
    *,
    user_email: str,
    user_name: str,
    booking_id: int,
) -> None:
    _render_and_send(
        template_name="cancellation",
        to_email=user_email,
        subject="Booking Cancellation",
        context={
            "user_name": user_name,
            "booking_id": booking_id,
        },
    )


def send_booking_reminder_email(
    *,
    user_email: str,
    user_name: str,
    booking_id: int,
    room_name: str,
    start_time: datetime,
) -> None:
    _render_and_send(
        template_name="reminder",
        to_email=user_email,
        subject="Upcoming Booking Reminder",
        context={
            "user_name": user_name,
            "booking_id": booking_id,
            "room_name": room_name,
            "start_time": start_time,
        },
    )


def send_email(
    *,
    to_email: str,
    subject: str,
    body: str,
) -> None:
    message = _build_message(
        to_email=to_email,
        subject=subject,
        text_body=body,
        html_body=body.replace("\n", "<br>"),
    )
    _send_message(message)
