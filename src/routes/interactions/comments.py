from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel, UserGroupModel, UserGroupEnum
from database.models.interactions import (
    CommentModel,
    CommentReactionModel,
    ReactionTypeEnum,
    NotificationModel,
    NotificationTypeEnum,
)
from database.models.movies import MovieModel
from schemas.movies import (
    CommentResponseSchema,
    CommentRequestSchema,
    CommentListResponseSchema,
    CommentReplyResponseSchema,
    CommentReactionResponseSchema,
    CommentReactionRequestSchema,
)
from security.dependencies import get_current_user

router = APIRouter(
    prefix="/movies",
    tags=["Comments"],
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
        "Pass `parent_id` to reply to a top-level comment of the same movie "
        "(replying to a reply is not allowed). A reply to someone else's "
        "comment sends a notification to the author of the parent comment. "
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

    comment_with_parent = None

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
    await db.flush()

    if comment_with_parent and comment_with_parent.user_id != current_user.id:
        db.add(
            NotificationModel(
                recipient_id=comment_with_parent.user_id,
                sender_id=current_user.id,
                comment_id=comment.id,
                notification_type=NotificationTypeEnum.COMMENT_REPLY,
            )
        )
    await db.commit()
    await db.refresh(comment)

    return CommentResponseSchema.model_validate(comment)


@router.get(
    "/{movie_id}/comments/",
    summary="List comments of a movie",
    description=(
        "Returns a paginated list of top-level comments for the movie, "
        "newest first. Each comment contains its replies (oldest first) "
        "and the number of likes and dislikes (`likes_count`, "
        "`dislikes_count`) for itself and for each reply. Pagination counts "
        "only top-level comments. Publicly accessible, no authentication "
        "required."
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
        .where(
            CommentModel.movie_id == movie_id,
            CommentModel.parent_id.is_(None),
        )
        .order_by(CommentModel.created_at.desc(), CommentModel.id.desc())
        .offset(offset)
        .limit(per_page)
    )
    comments = stmt.all()

    parent_ids = [comment.id for comment in comments]

    replies_by_parent = {}
    if parent_ids:
        replies_result = await db.scalars(
            select(CommentModel)
            .where(
                CommentModel.parent_id.in_(parent_ids),
            )
            .order_by(CommentModel.created_at.asc(), CommentModel.id.asc())
        )
        for reply in replies_result.all():
            replies_by_parent.setdefault(reply.parent_id, []).append(reply)

    all_comments_ids = parent_ids + [
        reply.id for replies in replies_by_parent.values() for reply in replies
    ]

    counts_by_comment = {}
    if all_comments_ids:
        counts_result = await db.execute(
            select(
                CommentReactionModel.comment_id,
                CommentReactionModel.reaction_type,
                func.count(),
            )
            .where(CommentReactionModel.comment_id.in_(all_comments_ids))
            .group_by(
                CommentReactionModel.comment_id,
                CommentReactionModel.reaction_type,
            )
        )
        for comment_id, reaction_type, count in counts_result.all():
            counts_by_comment.setdefault(comment_id, {})[reaction_type] = count

    def get_counts(comment_id: int) -> dict[str, int]:
        """Return the likes and dislikes counts for a comment, 0 when it has no reactions."""

        counts = counts_by_comment.get(comment_id, {})
        return {
            "likes_count": counts.get(ReactionTypeEnum.LIKE, 0),
            "dislikes_count": counts.get(ReactionTypeEnum.DISLIKE, 0),
        }

    count_stmt = (
        select(func.count())
        .select_from(CommentModel)
        .where(
            CommentModel.movie_id == movie_id, CommentModel.parent_id.is_(None)
        )
    )
    result_count = await db.execute(count_stmt)
    total_items = result_count.scalar() or 0

    total_pages = (total_items + per_page - 1) // per_page
    prev_page_number = min(page - 1, total_pages)

    items = [
        CommentResponseSchema.model_validate(comment).model_copy(
            update={
                **get_counts(comment.id),
                "replies": [
                    CommentReplyResponseSchema.model_validate(
                        reply
                    ).model_copy(update=get_counts(reply.id))
                    for reply in replies_by_parent.get(comment.id, [])
                ],
            }
        )
        for comment in comments
    ]

    return CommentListResponseSchema(
        comments=items,
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


@router.put(
    "/{movie_id}/comments/{comment_id}/reaction/",
    summary="Like or dislike a comment",
    description=(
        "Sets the current user's reaction (like or dislike) to the comment. "
        "If the user has already reacted to this comment, the reaction is "
        "replaced. A new like on someone else's comment sends a notification "
        "to the comment's author. Authentication required."
    ),
    response_model=CommentReactionResponseSchema,
    status_code=200,
    responses={
        401: UNAUTHORIZED_RESPONSE,
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
async def put_reaction_comment(
    movie_id: int,
    comment_id: int,
    reaction_data: CommentReactionRequestSchema,
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

    reaction = await db.scalar(
        select(CommentReactionModel).where(
            CommentReactionModel.comment_id == comment_id,
            CommentReactionModel.user_id == current_user.id,
        )
    )
    should_notify = False

    try:
        if not reaction:
            reaction = CommentReactionModel(
                comment_id=comment_id,
                user_id=current_user.id,
                reaction_type=reaction_data.reaction_type,
            )
            db.add(reaction)
            should_notify = (
                reaction_data.reaction_type == ReactionTypeEnum.LIKE
            )
        else:
            was_like = reaction.reaction_type == ReactionTypeEnum.LIKE
            reaction.reaction_type = reaction_data.reaction_type
            should_notify = (
                reaction_data.reaction_type == ReactionTypeEnum.LIKE
                and not was_like
            )

        if should_notify and db_comment.user_id != current_user.id:
            db.add(
                NotificationModel(
                    recipient_id=db_comment.user_id,
                    sender_id=current_user.id,
                    comment_id=comment_id,
                    notification_type=NotificationTypeEnum.COMMENT_LIKE,
                )
            )
        await db.commit()
        await db.refresh(reaction)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid input data.")

    return CommentReactionResponseSchema.model_validate(reaction)


@router.delete(
    "/{movie_id}/comments/{comment_id}/reaction/",
    summary="Remove my reaction to a comment",
    description=(
        "Removes the current user's like or dislike for the comment. "
        "Authentication required."
    ),
    status_code=204,
    responses={
        401: UNAUTHORIZED_RESPONSE,
        404: {
            "description": "Comment or reaction not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Reaction not found"}
                }
            },
        },
    },
)
async def delete_reaction_comment(
    movie_id: int,
    comment_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):

    comment = await db.scalar(
        select(CommentModel).where(
            CommentModel.movie_id == movie_id, CommentModel.id == comment_id
        )
    )

    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    reaction = await db.scalar(
        select(CommentReactionModel).where(
            CommentReactionModel.comment_id == comment_id,
            CommentReactionModel.user_id == current_user.id,
        )
    )
    if not reaction:
        raise HTTPException(status_code=404, detail="Reaction not found")

    await db.delete(reaction)
    await db.commit()
    return
