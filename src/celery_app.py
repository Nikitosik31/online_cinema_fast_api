"""Celery application and the periodic task schedule."""

from celery import Celery
from celery.schedules import crontab

from config.config import get_settings

settings = get_settings()

celery_app = Celery(
    "online_cinema",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["tasks"],
)

celery_app.conf.beat_schedule = {
    "delete_expired_tokens": {
        "task": "tasks.delete_expired_tokens",
        "schedule": crontab(minute=0, hour="*/6"),
    }
}
