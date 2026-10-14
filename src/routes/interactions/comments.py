from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel, UserGroupModel, UserGroupEnum
from database.models.interactions import CommentModel
from database.models.movies import MovieModel
from schemas.movies import (
    CommentResponseSchema,
    CommentRequestSchema,
    CommentListResponseSchema,
)
from security.dependencies import get_current_user

router = APIRouter(
    prefix="/movies",
)

UNAUTHORIZED_RESPONSE = {
    "description": "Not authenticated or invalid/expired token.",
    "content": {
        "application/json": {"example": {"detail": "Token is invalid."}}
    },
}


@router.post(
    "/{movie_id}/comments/",
    summary="Add a comment to a movie",
    description=(
        "Creates a new comment on the movie on behalf of the current user. "
        "Authentication required."
    ),
    response_model=CommentResponseSchema,
    status_code=201,
    responses={
        401: UNAUTHORIZED_RESPONSE,
        400: {
            "description": "Cannot reply to a reply",
            "content": {
                "application/json": {
                    "example": {"detail": "Cannot reply to a reply"}
                }
            },
        },
        404: {
            "description": "Movie or parent comment not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Parent comment not found"}
                }
            },
        },
    },
)
async def add_comment(
    movie_id: int,
    comment_data: CommentRequestSchema,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    db_movie = await db.scalar(
        select(MovieModel).where(MovieModel.id == movie_id)
    )
    if not db_movie:
        raise HTTPException(
            status_code=404, detail="Movie with this id does not exist"
        )

    if comment_data.parent_id:
        comment_with_parent = await db.scalar(
            select(CommentModel).where(
                CommentModel.movie_id == movie_id,
                CommentModel.id == comment_data.parent_id,
            )
        )
        if not comment_with_parent:
            raise HTTPException(
                status_code=404, detail="Parent comment not found"
            )
        if comment_with_parent.parent_id is not None:
            raise HTTPException(
                status_code=400, detail="Cannot reply to a reply"
            )

    comment = CommentModel(
        user_id=current_user.id,
        movie_id=movie_id,
        content=comment_data.content,
        parent_id=comment_data.parent_id,
    )

    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return CommentResponseSchema.model_validate(comment)


@router.get(
    "/{movie_id}/comments/",
    summary="List comments of a movie",
    description=(
        "Returns a paginated list of comments for the movie, "
        "newest first. Publicly accessible, no authentication required."
    ),
    response_model=CommentListResponseSchema,
    status_code=200,
    responses={
        404: {
            "description": "Movie with this id does not exist",
            "content": {
                "application/json": {
                    "example": {"detail": "Movie with this id does not exist"}
                }
            },
        },
    },
)
async def list_comments(
    movie_id: int,
    db: AsyncSession = Depends(get_postgresql_db),
    page: int = Query(1, ge=1, description="Page number (1-based index)"),
    per_page: int = Query(
        10, ge=1, le=20, description="Number of items per page (max 20)"
    ),
):
    db_movie = await db.scalar(
        select(MovieModel).where(MovieModel.id == movie_id)
    )
    if not db_movie:
        raise HTTPException(
            status_code=404, detail="Movie with this id does not exist"
        )

    offset = (page - 1) * per_page
    stmt = await db.scalars(
        select(CommentModel)
        .where(CommentModel.movie_id == movie_id)
        .order_by(CommentModel.created_at.desc(), CommentModel.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    comments = stmt.all()

    count_stmt = (
        select(func.count())
        .select_from(CommentModel)
        .where(CommentModel.movie_id == movie_id)
    )
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    total_pages = (total_items + per_page - 1) // per_page
    prev_page_number = min(page - 1, total_pages)

    return CommentListResponseSchema(
        comments=comments,
        prev_page=(
            f"/movies/{movie_id}/comments/?page={prev_page_number}&per_page={per_page}"
            if prev_page_number >= 1
            else None
        ),
        next_page=(
            f"/movies/{movie_id}/comments/?page={page+1}&per_page={per_page}"
            if page < total_pages
            else None
        ),
        total_pages=total_pages,
        total_items=total_items,
    )


@router.delete(
    "/{movie_id}/comments/{comment_id}/",
    summary="Delete a comment",
    description=(
        "Deletes a comment. The author can delete their own comment; "
        "moderators and administrators can delete any comment. "
        "Authentication required."
    ),
    status_code=204,
    responses={
        401: UNAUTHORIZED_RESPONSE,
        403: {
            "description": "The user is neither the author nor a moderator",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "You do not have permission to delete this comment"
                    }
                }
            },
        },
        404: {
            "description": "Comment not found for this movie",
            "content": {
                "application/json": {
                    "example": {"detail": "Comment not found"}
                }
            },
        },
    },
)
async def delete_comment(
    movie_id: int,
    comment_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    db_comment = await db.scalar(
        select(CommentModel).where(
            CommentModel.movie_id == movie_id, CommentModel.id == comment_id
        )
    )
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    group = await db.scalar(
        select(UserGroupModel).where(
            UserGroupModel.id == current_user.group_id
        )
    )
    is_author = db_comment.user_id == current_user.id
    is_moderator = group.name in (UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN)

    if not (is_author or is_moderator):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to delete this comment",
        )

    await db.delete(db_comment)
    await db.commit()
    return
