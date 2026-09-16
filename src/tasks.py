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
    asyncio.run(_delete_expired_tokens())
