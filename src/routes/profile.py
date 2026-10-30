import logging

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import get_postgresql_db
from database.models.accounts import UserModel, UserProfileModel
from schemas.profile import ProfileResponseSchema, ProfileUpdateRequestSchema
from security.dependencies import get_current_user
from storage.minio import (
    build_avatar_url,
    AVATAR_EXTENSIONS,
    delete_avatar,
    upload_avatar,
)

logger = logging.getLogger(__name__)

MAX_AVATAR_SIZE = 2 * 1024 * 1024


router = APIRouter(
    prefix="/profile",
    tags=["Profile"],
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


async def get_or_create_profile(
    current_user: UserModel, db: AsyncSession
) -> UserProfileModel:
    profile = await db.scalar(
        select(UserProfileModel).where(
            UserProfileModel.user_id == current_user.id
        )
    )

    if not profile:
        try:
            profile = UserProfileModel(
                user_id=current_user.id,
            )
            db.add(profile)
            await db.commit()
            await db.refresh(profile)

        except IntegrityError:
            await db.rollback()
            profile = await db.scalar(
                select(UserProfileModel).where(
                    UserProfileModel.user_id == current_user.id
                )
            )
    return profile


def to_response(profile: UserProfileModel) -> ProfileResponseSchema:
    return ProfileResponseSchema(
        first_name=profile.first_name,
        last_name=profile.last_name,
        gender=profile.gender,
        date_of_birth=profile.date_of_birth,
        info=profile.info,
        avatar_url=build_avatar_url(profile.avatar),
    )


@router.get(
    "/",
    summary="Get my profile",
    description=(
        "Returns the current user's profile: name, gender, date of birth, "
        "info and the public URL of the avatar. If the user has not filled "
        "in the profile yet, an empty profile is created on the first call, "
        "so every field is `null`. Authentication required."
    ),
    response_model=ProfileResponseSchema,
    status_code=200,
)
async def get_profile(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    """
    Return the profile of the current user.

    The profile is created lazily: if the user has none, an empty one is
    saved and returned. The avatar is stored in MinIO as an object key; the
    response contains the ready-to-open `avatar_url` instead, or `null` if
    the user has no avatar.

    Args:
        current_user (UserModel): The authenticated user (injected).
        db (AsyncSession): Database session (injected).

    Returns:
        ProfileResponseSchema: The profile fields and the avatar URL.
    """
    user_profile = await get_or_create_profile(current_user, db)
    return to_response(user_profile)


@router.patch(
    "/",
    summary="Update my profile",
    description=(
        "Partially updates the current user's profile. Send only the fields "
        "you want to change: fields that are left out stay untouched, and a "
        "field sent as `null` is cleared. The avatar is changed with a "
        "separate endpoint. Authentication required."
    ),
    response_model=ProfileResponseSchema,
    status_code=200,
    responses={
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "value_error",
                                "loc": ["body", "date_of_birth"],
                                "msg": (
                                    "Value error, Date of birth cannot be "
                                    "in the future"
                                ),
                            }
                        ]
                    }
                }
            },
        },
    },
)
async def update_profile(
    data: ProfileUpdateRequestSchema,
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    """
    Update the profile of the current user.

    Only the fields present in the request body are changed. A field that is
    omitted keeps its value; a field sent as `null` is cleared. If the user
    has no profile yet, an empty one is created first.

    Validation rules: names are 1-50 characters, `info` is up to 1000
    characters, `gender` is `man` or `woman`, and the date of birth cannot
    be in the future.

    Args:
        data (ProfileUpdateRequestSchema): The fields to change.
        current_user (UserModel): The authenticated user (injected).
        db (AsyncSession): Database session (injected).

    Returns:
        ProfileResponseSchema: The updated profile.
    """
    user_profile = await get_or_create_profile(current_user, db)
    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(user_profile, field, value)

    await db.commit()
    await db.refresh(user_profile)
    return to_response(user_profile)


@router.put(
    "/avatar/",
    summary="Upload my avatar",
    description=(
        "Uploads a new avatar for the current user and replaces the old one. "
        "Send the image as `multipart/form-data` in the `file` field. "
        "Allowed types: JPEG, PNG and WebP; the maximum size is 2 MB. "
        "Authentication required."
    ),
    response_model=ProfileResponseSchema,
    status_code=200,
    responses={
        400: {
            "description": "The uploaded file is empty",
            "content": {
                "application/json": {
                    "example": {"detail": "The uploaded file is empty"}
                }
            },
        },
        413: {
            "description": "The file is larger than 2 MB",
            "content": {
                "application/json": {
                    "example": {"detail": "The file is too large (max 2 MB)"}
                }
            },
        },
        415: {
            "description": "The file type is not supported",
            "content": {
                "application/json": {
                    "example": {
                        "detail": (
                            "Unsupported file type. " "Use JPEG, PNG or WebP"
                        )
                    }
                }
            },
        },
        502: {
            "description": "The file storage is unavailable",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not store the avatar"}
                }
            },
        },
    },
)
async def upload_profile_avatar(
    file: UploadFile = File(..., description="Image file: JPEG, PNG or WebP"),
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    """
    Upload an avatar for the current user.

    The file type and size are checked first. The image is stored in MinIO
    under a new random name, so the avatar URL changes with every upload and
    browsers never show an outdated picture. Only after the profile is saved
    is the previous avatar deleted from the storage.

    Args:
        file (UploadFile): The image file (JPEG, PNG or WebP, up to 2 MB).
        current_user (UserModel): The authenticated user (injected).
        db (AsyncSession): Database session (injected).

    Returns:
        ProfileResponseSchema: The profile with the new `avatar_url`.

    Raises:
        HTTPException: 415 if the type is not supported, 400 if the file is
            empty, 413 if it is too large, 502 if the storage fails.
    """
    if file.content_type not in AVATAR_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Use JPEG, PNG or WebP",
        )

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=400,
            detail="The uploaded file is empty",
        )

    if len(data) > MAX_AVATAR_SIZE:
        raise HTTPException(
            status_code=413,
            detail="The file is too large (max 2 MB)",
        )

    user_profile = await get_or_create_profile(current_user, db)
    old_key = user_profile.avatar
    try:
        new_key = await upload_avatar(current_user.id, data, file.content_type)
    except Exception:
        logger.exception(
            "Could not upload the avatar of user %s", current_user.id
        )
        raise HTTPException(
            status_code=502, detail="Could not store the avatar"
        )

    user_profile.avatar = new_key
    await db.commit()
    await db.refresh(user_profile)

    if old_key:
        try:
            await delete_avatar(old_key)
        except Exception:
            logger.exception("Could not delete the old avatar %s", old_key)

    return to_response(user_profile)


@router.delete(
    "/avatar/",
    summary="Delete my avatar",
    description=(
        "Removes the current user's avatar. The profile's `avatar_url` "
        "becomes `null`. If the user has no avatar, nothing happens and the "
        "response is still 204. Authentication required."
    ),
    status_code=204,
)
async def delete_profile_avatar(
    current_user: UserModel = Depends(get_current_user),
    db: AsyncSession = Depends(get_postgresql_db),
):
    """
    Delete the avatar of the current user.

    The reference is cleared in the database first, and only then is the
    file deleted from the storage. A failure to delete the file is logged
    but does not fail the request, because the avatar is already gone from
    the profile.

    Args:
        current_user (UserModel): The authenticated user (injected).
        db (AsyncSession): Database session (injected).
    """
    user_profile = await get_or_create_profile(current_user, db)
    if not user_profile.avatar:
        return

    old_key = user_profile.avatar
    user_profile.avatar = None
    await db.commit()

    try:
        await delete_avatar(old_key)
    except Exception:
        logger.exception("Could not delete the old avatar %s", old_key)
