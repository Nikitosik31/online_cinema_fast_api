from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from database.database import get_postgresql_db
from database.models.accounts import UserModel
from schemas.accounts import MessageResponseSchema
from security.dependencies import require_admin

router = APIRouter(prefix="/admin")


@router.patch("/users/{user_id}/activate/", status_code=status.HTTP_200_OK)
async def activate_user_by_admin(
    user_id: int,
    db: AsyncSession = Depends(get_postgresql_db),
    current_user: UserModel = Depends(require_admin),
):
    stmt = select(UserModel).where(UserModel.id == user_id)
    user = await db.scalar(stmt)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    user.is_active = True
    await db.commit()
    return MessageResponseSchema(
        message="User has been activated",
    )
