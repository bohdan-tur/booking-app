import asyncio
from datetime import datetime, timedelta

from sqlalchemy import delete, select, update
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


@celery_app.task(bind=True, max_retries=3, name="process_booking_creation")
def process_booking_creation(
    self,
    booking_id: int,
    user_id: int,
    room_id: int,
    start_time: datetime,
    end_time: datetime,
):
    async def fetch_booking_data() -> dict | None:
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
                return None

            booking, user, room = booking_data
            return {
                "user_email": user.email,
                "user_name": user.username,
                "booking_id": booking.id,
                "room_name": room.name,
                "start_time": booking.start_time,
                "end_time": booking.end_time,
            }

    async def process_booking():
        try:
            data = await fetch_booking_data()

            if not data:
                logger.error(f"Booking {booking_id} not found")
                return {"status": "error", "message": "Booking not found"}

            email_sent = await asyncio.to_thread(
                send_booking_confirmation_email,
                user_email=data["user_email"],
                user_name=data["user_name"],
                booking_id=data["booking_id"],
                room_name=data["room_name"],
                start_time=data["start_time"],
                end_time=data["end_time"],
            )

            if email_sent:
                logger.info(f"Confirmation email sent for booking {booking_id}")
                return {"status": "success", "email_sent": True}

            logger.error(f"Failed to send email for booking {booking_id}")
            return {"status": "success", "email_sent": False}

        except Exception as exc:
            logger.error(f"Error processing booking {booking_id}: {exc}")
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=60 * (self.request.retries + 1))
            return {"status": "error", "message": str(exc)}

    return asyncio.run(process_booking())


@celery_app.task(bind=True, max_retries=3)
def process_booking_cancellation(self, booking_id: int, user_id: int):
    async def fetch_user_data() -> dict | None:
        async with CelerySessionLocal() as session:
            stmt = select(Users).where(Users.id == user_id)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return None

            return {
                "email": user.email,
                "username": user.username,
            }

    async def process_cancellation():
        try:
            user_data = await fetch_user_data()

            if not user_data:
                logger.error(f"User {user_id} not found")
                return {"status": "error", "message": "User not found"}

            email_sent = await asyncio.to_thread(
                send_booking_cancellation_email,
                user_email=user_data["email"],
                user_name=user_data["username"],
                booking_id=booking_id,
            )

            if email_sent:
                logger.info(f"Cancellation email sent for booking {booking_id}")
                return {"status": "success", "email_sent": True}

            logger.error(f"Failed to send cancellation email for booking {booking_id}")
            return {"status": "success", "email_sent": False}

        except Exception as exc:
            logger.error(f"Error processing booking cancellation {booking_id}: {exc}")
            if self.request.retries < self.max_retries:
                raise self.retry(countdown=60 * (self.request.retries + 1))
            return {"status": "error", "message": str(exc)}

    return asyncio.run(process_cancellation())


@celery_app.task
def update_expired_bookings():
    async def update_statuses():
        async with CelerySessionLocal() as session:
            try:
                current_time = datetime.now()

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

                updated_count = result.rowcount

                if updated_count > 0:
                    logger.info(
                        f"Updated {updated_count} booking statuses to 'expired'"
                    )

                return updated_count

            except Exception as e:
                logger.error(f"Error updating booking statuses: {e}")
                await session.rollback()
                return 0

    return asyncio.run(update_statuses())


@celery_app.task
def send_daily_reminders():
    async def fetch_reminders_data() -> list[dict]:
        async with CelerySessionLocal() as session:
            tomorrow = datetime.now() + timedelta(days=1)
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

            return [
                {
                    "user_email": user.email,
                    "user_name": user.username,
                    "booking_id": booking.id,
                    "room_name": room.name,
                    "start_time": booking.start_time,
                }
                for booking, user, room in bookings_data
            ]

    async def process_reminders():
        try:
            reminders_data = await fetch_reminders_data()
            reminders_sent = 0

            for data in reminders_data:
                try:
                    email_sent = await asyncio.to_thread(
                        send_booking_reminder_email,
                        user_email=data["user_email"],
                        user_name=data["user_name"],
                        booking_id=data["booking_id"],
                        room_name=data["room_name"],
                        start_time=data["start_time"],
                    )

                    if email_sent:
                        reminders_sent += 1
                        logger.info(f"Reminder sent for booking {data['booking_id']}")
                    else:
                        logger.error(
                            f"Failed to send reminder for booking {data['booking_id']}"
                        )

                except Exception as e:
                    logger.error(
                        f"Error sending reminder for booking {data['booking_id']}: {e}"
                    )

            if reminders_sent > 0:
                logger.info(f"Sent {reminders_sent} reminders")

            return reminders_sent

        except Exception as e:
            logger.error(f"Error processing daily reminders: {e}")
            return 0

    return asyncio.run(process_reminders())


@celery_app.task
def cleanup_old_bookings():
    async def cleanup():
        async with CelerySessionLocal() as session:
            try:
                one_year_ago = datetime.now() - timedelta(days=365)

                stmt = delete(Bookings).where(
                    Bookings.end_time < one_year_ago,
                    Bookings.status == "expired",
                )

                result = await session.execute(stmt)
                await session.commit()

                deleted_count = result.rowcount

                if deleted_count > 0:
                    logger.info(f"Deleted {deleted_count} old bookings")

                return deleted_count

            except Exception as e:
                logger.error(f"Error cleaning up old bookings: {e}")
                await session.rollback()
                return 0

    return asyncio.run(cleanup())


@celery_app.task
def generate_daily_statistics():
    async def fetch_statistics_data() -> dict:
        async with CelerySessionLocal() as session:
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = today + timedelta(days=1)

            stmt = select(Bookings).where(
                Bookings.start_time >= today,
                Bookings.start_time < tomorrow,
            )
            today_bookings = len((await session.execute(stmt)).scalars().all())

            stmt = select(Bookings).where(Bookings.status == "active")
            active_bookings = len((await session.execute(stmt)).scalars().all())

            week_ago = datetime.now() - timedelta(days=7)
            stmt = select(Bookings).where(
                Bookings.end_time >= week_ago,
                Bookings.status == "completed",
            )
            completed_bookings = len((await session.execute(stmt)).scalars().all())

            stmt = select(Users).where(Users.role == "admin")
            admins = (await session.execute(stmt)).scalars().all()

            return {
                "today_bookings": today_bookings,
                "active_bookings": active_bookings,
                "completed_bookings": completed_bookings,
                "admin_emails": [admin.email for admin in admins],
            }

    async def process_statistics():
        try:
            stats = await fetch_statistics_data()

            report = f"""
Daily Report ({datetime.now().strftime("%d.%m.%Y")})

Statistics:
• New bookings today: {stats["today_bookings"]}
• Active bookings: {stats["active_bookings"]}
• Completed in the last 7 days: {stats["completed_bookings"]}

More detailed statistics are available in the admin panel.
"""

            admins_notified = 0

            for email in stats["admin_emails"]:
                try:
                    await asyncio.to_thread(
                        send_email,
                        to_email=email,
                        subject=f"Daily Report - {datetime.now().strftime('%d.%m.%Y')}",
                        body=report,
                    )
                    admins_notified += 1
                    logger.info(f"Daily report sent to admin {email}")

                except Exception as e:
                    logger.error(f"Error sending daily report to admin {email}: {e}")

            return {
                "today_bookings": stats["today_bookings"],
                "active_bookings": stats["active_bookings"],
                "completed_bookings": stats["completed_bookings"],
                "admins_notified": admins_notified,
            }

        except Exception as e:
            logger.error(f"Error processing daily statistics: {e}")
            return {"error": str(e)}

    return asyncio.run(process_statistics())
