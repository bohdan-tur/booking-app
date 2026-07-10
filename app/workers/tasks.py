import asyncio
from datetime import datetime, timedelta
from sqlalchemy import select, update, delete

from app.workers.app import celery_app
from app.db.database import AsyncSessionLocal
from app.models.booking_model import Bookings
from app.models.user_model import Users
from app.models.room_model import Rooms
from app.core.logger import logger
from app.services.email import (
    send_booking_confirmation_email,
    send_booking_cancellation_email,
    send_booking_reminder_email,
    send_email,
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
    async def process_booking():
        async with AsyncSessionLocal() as session:
            try:
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

                email_sent = send_booking_confirmation_email(
                    user_email=user.email,
                    user_name=user.username,
                    booking_id=booking.id,
                    room_name=room.name,
                    start_time=booking.start_time,
                    end_time=booking.end_time,
                )

                if email_sent:
                    logger.info(f"Confirmation email sent for booking {booking_id}")
                    return {"status": "success", "email_sent": True}
                else:
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
    async def process_cancellation():
        async with AsyncSessionLocal() as session:
            try:
                stmt = select(Users).where(Users.id == user_id)
                result = await session.execute(stmt)
                user = result.scalar_one_or_none()

                if not user:
                    logger.error(f"User {user_id} not found")
                    return {"status": "error", "message": "User not found"}

                email_sent = send_booking_cancellation_email(
                    user_email=user.email,
                    user_name=user.username,
                    booking_id=booking_id,
                )

                if email_sent:
                    logger.info(f"Cancellation email sent for booking {booking_id}")
                    return {"status": "success", "email_sent": True}
                else:
                    logger.error(
                        f"Failed to send cancellation email for booking {booking_id}"
                    )
                    return {"status": "success", "email_sent": False}

            except Exception as exc:
                logger.error(
                    f"Error processing booking cancellation {booking_id}: {exc}"
                )
                if self.request.retries < self.max_retries:
                    raise self.retry(countdown=60 * (self.request.retries + 1))
                return {"status": "error", "message": str(exc)}

    return asyncio.run(process_cancellation())


@celery_app.task
def update_expired_bookings():
    async def update_statuses():
        async with AsyncSessionLocal() as session:
            try:
                current_time = datetime.now()

                stmt = (
                    update(Bookings)
                    .where(
                        Bookings.end_time < current_time, Bookings.status == "active"
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
    async def send_reminders():
        async with AsyncSessionLocal() as session:
            try:
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

                reminders_sent = 0
                for booking, user, room in bookings_data:
                    try:
                        email_sent = send_booking_reminder_email(
                            user_email=user.email,
                            user_name=user.username,
                            booking_id=booking.id,
                            room_name=room.name,
                            start_time=booking.start_time,
                        )

                        if email_sent:
                            reminders_sent += 1
                            logger.info(f"Reminder sent for booking {booking.id}")
                        else:
                            logger.error(
                                f"Failed to send reminder for booking {booking.id}"
                            )

                    except Exception as e:
                        logger.error(
                            f"Error sending reminder for booking {booking.id}: {e}"
                        )

                if reminders_sent > 0:
                    logger.info(f"Sent {reminders_sent} reminders")

                return reminders_sent

            except Exception as e:
                logger.error(f"Error sending reminders: {e}")
                return 0

    return asyncio.run(send_reminders())


@celery_app.task
def cleanup_old_bookings():
    async def cleanup():
        async with AsyncSessionLocal() as session:
            try:
                one_year_ago = datetime.now() - timedelta(days=365)

                stmt = delete(Bookings).where(
                    Bookings.end_time < one_year_ago, Bookings.status == "expired"
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
    async def generate_stats():
        async with AsyncSessionLocal() as session:
            try:
                today = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                tomorrow = today + timedelta(days=1)

                stmt = select(Bookings).where(
                    Bookings.start_time >= today, Bookings.start_time < tomorrow
                )
                result = await session.execute(stmt)
                today_bookings = len(result.scalars().all())

                stmt = select(Bookings).where(Bookings.status == "active")
                result = await session.execute(stmt)
                active_bookings = len(result.scalars().all())

                week_ago = datetime.now() - timedelta(days=7)
                stmt = select(Bookings).where(
                    Bookings.end_time >= week_ago, Bookings.status == "completed"
                )
                result = await session.execute(stmt)
                completed_bookings = len(result.scalars().all())

                stmt = select(Users).where(Users.role == "admin")
                result = await session.execute(stmt)
                admins = result.scalars().all()

                report = f"""
Daily Report ({datetime.now().strftime("%d.%m.%Y")})

Statistics:
• New bookings today: {today_bookings}
• Active bookings: {active_bookings}
• Completed in the last 7 days: {completed_bookings}

More detailed statistics are available in the admin panel.
"""

                for admin in admins:
                    try:
                        send_email(
                            to_email=admin.email,
                            subject=f"Daily Report - {datetime.now().strftime('%d.%m.%Y')}",
                            body=report,
                        )
                        logger.info(f"Daily report sent to admin {admin.email}")
                    except Exception as e:
                        logger.error(
                            f"Error sending daily report to admin {admin.email}: {e}"
                        )

                return {
                    "today_bookings": today_bookings,
                    "active_bookings": active_bookings,
                    "completed_bookings": completed_bookings,
                    "admins_notified": len(admins),
                }

            except Exception as e:
                logger.error(f"Error generating daily statistics: {e}")
                return {"error": str(e)}

    return asyncio.run(generate_stats())
