import asyncio
import smtplib
from datetime import UTC, datetime, timedelta
from typing import NoReturn

from celery import Task
from celery.utils.time import get_exponential_backoff_interval
from sqlalchemy import func, select, update
from sqlalchemy.exc import OperationalError as DatabaseOperationalError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.logger import logger
from app.models.booking import Booking
from app.models.booking_status import BookingStatus
from app.models.room import Room
from app.models.user import User
from app.services.email import (
    send_booking_cancellation_email,
    send_booking_confirmation_email,
    send_booking_reminder_email,
    send_email,
)
from app.workers.app import celery_app

celery_engine = create_async_engine(
    settings.DATABASE_URL,
    poolclass=NullPool,
)

CelerySessionLocal = async_sessionmaker(
    bind=celery_engine,
    expire_on_commit=False,
)

NOTIFICATION_RETRY_BASE_SECONDS = 60
NOTIFICATION_RETRY_MAX_SECONDS = 15 * 60
SMTP_TRANSIENT_MIN_CODE = 400
SMTP_PERMANENT_MIN_CODE = 500


def get_db_utc_time() -> datetime:
    return datetime.now(UTC)


def _is_transient_notification_error(exc: Exception) -> bool:
    if isinstance(exc, smtplib.SMTPResponseException):
        return SMTP_TRANSIENT_MIN_CODE <= exc.smtp_code < SMTP_PERMANENT_MIN_CODE
    if isinstance(exc, smtplib.SMTPServerDisconnected):
        return True
    if isinstance(exc, smtplib.SMTPException):
        return False
    return isinstance(exc, (OSError, DatabaseOperationalError))


def _handle_notification_failure(
    task: Task,
    exc: Exception,
    *,
    booking_id: int,
) -> NoReturn:
    if not _is_transient_notification_error(exc):
        logger.error(
            "Permanent booking notification failure: task=%s booking_id=%s error=%s",
            task.name,
            booking_id,
            type(exc).__name__,
        )
        raise exc

    countdown = max(
        1,
        get_exponential_backoff_interval(
            factor=NOTIFICATION_RETRY_BASE_SECONDS,
            retries=task.request.retries,
            maximum=NOTIFICATION_RETRY_MAX_SECONDS,
            full_jitter=True,
        ),
    )
    logger.warning(
        "Transient booking notification failure: task=%s booking_id=%s retry=%s",
        task.name,
        booking_id,
        task.request.retries + 1,
    )
    raise task.retry(countdown=countdown, exc=exc) from exc


@celery_app.task(bind=True, max_retries=3, name="process_booking_creation")
def process_booking_creation(self, booking_id: int):
    async def process():
        async with CelerySessionLocal() as session:
            stmt = (
                select(Booking, User, Room)
                .join(User)
                .join(Room)
                .where(Booking.id == booking_id)
            )
            result = await session.execute(stmt)
            booking_data = result.first()

            if not booking_data:
                logger.error(f"Booking {booking_id} not found")
                return {"status": "error", "message": "Booking not found"}

            booking, user, room = booking_data
            if booking.status != BookingStatus.ACTIVE:
                logger.info(
                    "Skipped booking confirmation: booking_id=%s status=%s",
                    booking_id,
                    booking.status.value,
                )
                return {"status": "skipped", "reason": "booking_not_active"}

        await asyncio.to_thread(
            send_booking_confirmation_email,
            user_email=user.email,
            user_name=user.username,
            booking_id=booking.id,
            room_name=room.name,
            start_time=booking.start_time,
            end_time=booking.end_time,
        )

        logger.info(f"Confirmation email sent for booking {booking_id}")
        return {"status": "success"}

    try:
        return asyncio.run(process())
    except (OSError, smtplib.SMTPException, SQLAlchemyError) as exc:
        _handle_notification_failure(self, exc, booking_id=booking_id)


@celery_app.task(bind=True, max_retries=3)
def process_booking_cancellation(self, booking_id: int):
    async def process():
        async with CelerySessionLocal() as session:
            stmt = select(Booking, User).join(User).where(Booking.id == booking_id)
            result = await session.execute(stmt)
            booking_data = result.first()

            if not booking_data:
                logger.error(f"User for cancelled booking {booking_id} not found")
                return {"status": "error"}

            booking, user = booking_data
            if booking.status != BookingStatus.CANCELLED:
                logger.info(
                    "Skipped booking cancellation notification: "
                    "booking_id=%s status=%s",
                    booking_id,
                    booking.status.value,
                )
                return {"status": "skipped", "reason": "booking_not_cancelled"}

        await asyncio.to_thread(
            send_booking_cancellation_email,
            user_email=user.email,
            user_name=user.username,
            booking_id=booking_id,
        )

        logger.info(f"Cancellation email sent for booking {booking_id}")
        return {"status": "success"}

    try:
        return asyncio.run(process())
    except (OSError, smtplib.SMTPException, SQLAlchemyError) as exc:
        _handle_notification_failure(self, exc, booking_id=booking_id)


@celery_app.task
def complete_finished_bookings():
    async def update_statuses():
        async with CelerySessionLocal() as session:
            try:
                current_time = get_db_utc_time()

                stmt = (
                    update(Booking)
                    .where(
                        Booking.end_time < current_time,
                        Booking.status == BookingStatus.ACTIVE,
                    )
                    .values(status=BookingStatus.COMPLETED)
                )

                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"Completed {result.rowcount} finished bookings")

                return result.rowcount

            except SQLAlchemyError:
                logger.exception("Error updating booking statuses")
                await session.rollback()
                return 0

    return asyncio.run(update_statuses())


@celery_app.task
def send_daily_reminders():
    async def process_reminders():
        async with CelerySessionLocal() as session:
            tomorrow = get_db_utc_time() + timedelta(days=1)
            start_of_tomorrow = tomorrow.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end_of_tomorrow = tomorrow.replace(
                hour=23, minute=59, second=59, microsecond=999999
            )

            stmt = (
                select(Booking, User, Room)
                .join(User)
                .join(Room)
                .where(
                    Booking.start_time >= start_of_tomorrow,
                    Booking.start_time <= end_of_tomorrow,
                    Booking.status == BookingStatus.ACTIVE,
                )
            )

            result = await session.execute(stmt)
            bookings_data = result.all()

        if not bookings_data:
            return 0

        email_tasks = [
            asyncio.to_thread(
                send_booking_reminder_email,
                user_email=user.email,
                user_name=user.username,
                booking_id=booking.id,
                room_name=room.name,
                start_time=booking.start_time,
            )
            for booking, user, room in bookings_data
        ]

        results = await asyncio.gather(*email_tasks, return_exceptions=True)

        reminders_sent = 0
        for (booking, _, _), res in zip(bookings_data, results, strict=True):
            if isinstance(res, Exception):
                logger.error(
                    "Error sending booking reminder: booking_id=%s error=%s",
                    booking.id,
                    type(res).__name__,
                )
            else:
                reminders_sent += 1
                logger.info(f"Reminder sent for booking {booking.id}")

        if reminders_sent > 0:
            logger.info(f"Sent {reminders_sent} reminders")

        return reminders_sent

    return asyncio.run(process_reminders())


@celery_app.task
def generate_daily_statistics():
    async def process_statistics():
        async with CelerySessionLocal() as session:
            today = get_db_utc_time().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)
            week_ago = get_db_utc_time() - timedelta(days=7)

            stmt_today = (
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.start_time >= today,
                    Booking.start_time < tomorrow,
                )
            )
            today_bookings = await session.scalar(stmt_today)

            stmt_active = (
                select(func.count())
                .select_from(Booking)
                .where(Booking.status == BookingStatus.ACTIVE)
            )
            active_bookings = await session.scalar(stmt_active)

            stmt_completed = (
                select(func.count())
                .select_from(Booking)
                .where(
                    Booking.end_time >= week_ago,
                    Booking.status == BookingStatus.COMPLETED,
                )
            )
            completed_bookings = await session.scalar(stmt_completed)

            stmt_admins = select(User).where(User.role == "admin")
            admins = (await session.execute(stmt_admins)).scalars().all()

        report = f"""
Daily Report ({get_db_utc_time().strftime("%d.%m.%Y")})

Statistics:
• New bookings today: {today_bookings or 0}
• Active bookings: {active_bookings or 0}
• Completed in the last 7 days: {completed_bookings or 0}

More detailed statistics are available in the admin panel.
"""
        admin_emails = [admin.email for admin in admins]
        if not admin_emails:
            return {"status": "no_admins"}

        email_tasks = [
            asyncio.to_thread(
                send_email,
                to_email=email,
                subject=f"Daily Report - {get_db_utc_time().strftime('%d.%m.%Y')}",
                body=report,
            )
            for email in admin_emails
        ]

        results = await asyncio.gather(*email_tasks, return_exceptions=True)

        admins_notified = 0
        for res in results:
            if isinstance(res, Exception):
                logger.error(
                    "Error sending daily report: error=%s",
                    type(res).__name__,
                )
            else:
                admins_notified += 1

        return {"admins_notified": admins_notified}

    return asyncio.run(process_statistics())
