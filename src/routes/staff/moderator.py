from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel
from routes.cart import build_cart_response
from schemas.cart import CartResponseSchema
from security.dependencies import require_moderator

router = APIRouter(
    prefix="/moderator",
    tags=["moderator"],
    dependencies=[Depends(require_moderator)],
    responses={
        401: {
            "description": "Not authenticated or invalid/expired token.",
            "content": {
                "application/json": {
                    "example": {"detail": "Token is invalid."}
                }
            },
        },
        403: {
            "description": "Moderator or administrator access required.",
            "content": {
                "application/json": {
                    "example": {"detail": "You are not a moderator"}
                }
            },
        },
    },
)


@router.get(
    "/carts/{user_id}/",
    summary="View a user's cart",
    description=(
        "Returns the contents of any user's cart for analysis or "
        "troubleshooting."
    ),
    response_model=CartResponseSchema,
    status_code=200,
    responses={
        404: {
            "description": "User not found",
            "content": {
                "application/json": {"example": {"detail": "User not found"}}
            },
        },
    },
)
async def moderator_get_cart(
    user_id: int,
    db: AsyncSession = Depends(get_postgresql_db),
):
    current_user = await db.scalar(
        select(UserModel).where(UserModel.id == user_id)
    )
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    return await build_cart_response(user_id, db)
