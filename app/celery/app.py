from celery import Celery
from app.core.config import settings
from app.logger import logger


if settings.TESTING:
    celery_app = Celery(
        "booking_app",
        broker="memory://",
        backend="cache+memory://",
        include=['app.tasks']
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
        include=['app.tasks']
    )

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    beat_schedule={
        'update-expired-bookings': {
            'task': 'app.tasks.update_expired_bookings',
            'schedule': 3600.0,
        },
        'send-daily-reminders': {
            'task': 'app.tasks.send_daily_reminders',
            'schedule': 86400.0,
        },
        'generate-daily-statistics': {
            'task': 'app.tasks.generate_daily_statistics',
            'schedule': 86400.0,
        },
    },
)






