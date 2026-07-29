import asyncio
import smtplib
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.logger import logger
from app.models.booking_model import Bookings
from app.models.room_model import Rooms
from app.models.user_model import Users
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


def get_db_utc_time() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@celery_app.task(bind=True, max_retries=3, name="process_booking_creation")
def process_booking_creation(self, booking_id: int):
    async def process():
        async with CelerySessionLocal() as session:
            stmt = (
                select(Bookings, Users, Rooms)
                .join(Users)
                .join(Rooms)
                .where(Bookings.id == booking_id)
            )
            result = await session.execute(stmt)
            booking_data = result.first()

            if not booking_data:
                logger.error(f"Booking {booking_id} not found")
                return {"status": "error", "message": "Booking not found"}

            booking, user, room = booking_data

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
        logger.exception("Error processing booking %s", booking_id)
        raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc) from exc


@celery_app.task(bind=True, max_retries=3)
def process_booking_cancellation(self, booking_id: int):
    async def process():
        async with CelerySessionLocal() as session:
            stmt = select(Users).join(Bookings).where(Bookings.id == booking_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                logger.error(f"User for cancelled booking {booking_id} not found")
                return {"status": "error"}

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
        logger.exception("Error processing booking cancellation %s", booking_id)
        raise self.retry(countdown=60 * (self.request.retries + 1), exc=exc) from exc


@celery_app.task
def update_expired_bookings():
    async def update_statuses():
        async with CelerySessionLocal() as session:
            try:
                current_time = get_db_utc_time()

                stmt = (
                    update(Bookings)
                    .where(
                        Bookings.end_time < current_time,
                        Bookings.status == "active",
                    )
                    .values(status="expired")
                )

                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(
                        f"Updated {result.rowcount} booking statuses to 'expired'"
                    )

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
                select(Bookings, Users, Rooms)
                .join(Users)
                .join(Rooms)
                .where(
                    Bookings.start_time >= start_of_tomorrow,
                    Bookings.start_time <= end_of_tomorrow,
                    Bookings.status == "active",
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
                logger.error(f"Error sending reminder for booking {booking.id}: {res}")
            else:
                reminders_sent += 1
                logger.info(f"Reminder sent for booking {booking.id}")

        if reminders_sent > 0:
            logger.info(f"Sent {reminders_sent} reminders")

        return reminders_sent

    return asyncio.run(process_reminders())


@celery_app.task
def cleanup_old_bookings():
    async def cleanup():
        async with CelerySessionLocal() as session:
            try:
                one_year_ago = get_db_utc_time() - timedelta(days=365)

                stmt = delete(Bookings).where(
                    Bookings.end_time < one_year_ago,
                    Bookings.status == "expired",
                )

                result = await session.execute(stmt)
                await session.commit()

                if result.rowcount > 0:
                    logger.info(f"Deleted {result.rowcount} old bookings")

                return result.rowcount

            except SQLAlchemyError:
                logger.exception("Error cleaning up old bookings")
                await session.rollback()
                return 0

    return asyncio.run(cleanup())


@celery_app.task
def generate_daily_statistics():
    async def process_statistics():
        async with CelerySessionLocal() as session:
            today = get_db_utc_time().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)
            week_ago = get_db_utc_time() - timedelta(days=7)

            stmt_today = (
                select(func.count())
                .select_from(Bookings)
                .where(
                    Bookings.start_time >= today,
                    Bookings.start_time < tomorrow,
                )
            )
            today_bookings = await session.scalar(stmt_today)

            stmt_active = (
                select(func.count())
                .select_from(Bookings)
                .where(Bookings.status == "active")
            )
            active_bookings = await session.scalar(stmt_active)

            stmt_completed = (
                select(func.count())
                .select_from(Bookings)
                .where(
                    Bookings.end_time >= week_ago,
                    Bookings.status == "completed",
                )
            )
            completed_bookings = await session.scalar(stmt_completed)

            stmt_admins = select(Users).where(Users.role == "admin")
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
        for email, res in zip(admin_emails, results, strict=True):
            if isinstance(res, Exception):
                logger.error(f"Error sending report to {email}: {res}")
            else:
                admins_notified += 1

        return {"admins_notified": admins_notified}

    return asyncio.run(process_statistics())
