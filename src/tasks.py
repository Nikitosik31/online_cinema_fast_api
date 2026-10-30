"""Background Celery tasks."""

import asyncio
from datetime import datetime

from sqlalchemy import delete

from celery_app import celery_app
from database.database import get_postgresql_db_contextmanager, engine
from database.models.accounts import (
    ActivationTokenModel,
    PasswordResetTokenModel,
)


async def _delete_expired_tokens() -> None:
    """
    Delete activation and password-reset tokens whose expiry time has passed.

    The engine is disposed at the end because every `asyncio.run()` creates a
    new event loop, and pooled connections cannot be reused across loops.
    """

    async with get_postgresql_db_contextmanager() as session:
        await session.execute(
            delete(ActivationTokenModel).where(
                ActivationTokenModel.expires_at < datetime.now()
            )
        )

        await session.execute(
            delete(PasswordResetTokenModel).where(
                PasswordResetTokenModel.expires_at < datetime.now()
            )
        )

        await session.commit()
    await engine.dispose()


@celery_app.task()
def delete_expired_tokens() -> None:
    """
    Celery task that removes expired activation and password-reset tokens.

    Scheduled by Celery beat every 6 hours (see `celery_app.py`). Runs the
    async cleanup in its own event loop.
    """

    asyncio.run(_delete_expired_tokens())
