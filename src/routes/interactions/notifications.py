from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel
from database.models.interactions import NotificationModel
from schemas.movies import (
    NotificationListResponseSchema,
    NotificationResponseSchema,
)
from security.dependencies import get_current_user

router = APIRouter(
    prefix="/notifications",
    responses={
        401: {
            "description": "Not authenticated or invalid/expired token.",
            "content": {
                "application/json": {
                    "example": {"detail": "Token is invalid."}
                }
            },
        }
    },
)


@router.get(
    "/",
    summary="List my notifications",
    description=(
        "Returns a paginated list of the current user's notifications "
        "(replies to their comments and likes on their comments), "
        "newest first. Authentication required."
    ),
    response_model=NotificationListResponseSchema,
    status_code=200,
)
async def list_notifications(
    page: int = Query(1, ge=1, description="Page number (1-based index)"),
    per_page: int = Query(
        10,
        ge=1,
        le=20,
        description="Number of items per page (max 20)",
    ),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    offset = (page - 1) * per_page

    stmt = await db.scalars(
        select(NotificationModel)
        .where(NotificationModel.recipient_id == current_user.id)
        .order_by(
            NotificationModel.created_at.desc(), NotificationModel.id.desc()
        )
        .offset(offset)
        .limit(per_page)
    )
    notifications = stmt.all()

    count_stmt = (
        select(func.count(NotificationModel.id))
        .select_from(NotificationModel)
        .where(NotificationModel.recipient_id == current_user.id)
    )
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    total_pages = (total_items + per_page - 1) // per_page
    prev_page_number = min(page - 1, total_pages)

    return NotificationListResponseSchema(
        notifications=[
            NotificationResponseSchema.model_validate(n) for n in notifications
        ],
        prev_page=(
            f"/notifications/?page={prev_page_number}&per_page={per_page}"
            if prev_page_number >= 1
            else None
        ),
        next_page=(
            f"/notifications/?page={page + 1}&per_page={per_page}"
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )
