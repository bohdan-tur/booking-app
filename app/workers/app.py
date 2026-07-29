from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

if settings.TESTING:
    celery_app = Celery(
        "booking_app",
        broker="memory://",
        backend="cache+memory://",
        include=["app.workers.tasks"],
    )
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
else:
    celery_app = Celery(
        "booking_app",
        broker=settings.REDIS_URL,
        backend=settings.REDIS_URL,
        include=["app.workers.tasks"],
    )

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.TIMEZONE,
    enable_utc=True,
    beat_schedule={
        "update-expired-bookings": {
            "task": "app.workers.tasks.update_expired_bookings",
            "schedule": 3600.0,
        },
        "send-daily-reminders": {
            "task": "app.workers.tasks.send_daily_reminders",
            "schedule": crontab(hour="9", minute="0"),
        },
        "generate-daily-statistics": {
            "task": "app.workers.tasks.generate_daily_statistics",
            "schedule": crontab(hour="23", minute="59"),
        },
    },
)
