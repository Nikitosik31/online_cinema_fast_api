"""Storing user files (avatars) in MinIO."""

import io
import json
from uuid import uuid4

from minio import Minio
from starlette.concurrency import run_in_threadpool

from config.config import get_settings

settings = get_settings()

client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False,
)

AVATAR_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _create_bucket() -> None:
    """Create the bucket if it does not exist and make its files public."""
    bucket = settings.minio_bucket
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)

    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"AWS": ["*"]},
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket}/*"],
            }
        ],
    }
    client.set_bucket_policy(bucket, json.dumps(policy))


async def ensure_bucket() -> None:
    """
    Make sure the avatars bucket exists and its files can be read publicly.

    Called once at application startup. Uploading and deleting files stay
    protected: only reading is public, so browsers can show the avatars by
    their URL.
    """
    await run_in_threadpool(_create_bucket)


async def upload_avatar(user_id: int, data: bytes, content_type: str) -> str:
    """
    Store an avatar image in the bucket.

    The object name contains a random part, so a new avatar always gets a new
    URL and browsers never show a cached old picture.

    Args:
        user_id (int): Id of the user who owns the avatar.
        data (bytes): The image file content.
        content_type (str): One of the keys of `AVATAR_EXTENSIONS`. The
            caller must check this before calling.

    Returns:
        str: The object key, for example `avatars/7/3f2a....jpg`. Store it in
            the profile instead of a full URL.
    """
    extension = AVATAR_EXTENSIONS[content_type]
    key = f"avatars/{user_id}/{uuid4().hex}.{extension}"
    await run_in_threadpool(
        client.put_object,
        settings.minio_bucket,
        key,
        io.BytesIO(data),
        len(data),
        content_type=content_type,
    )
    return key


async def delete_avatar(key: str) -> None:
    """
    Delete an avatar from the bucket.

    Deleting a key that does not exist is not an error.

    Args:
        key (str): The object key returned by `upload_avatar`.
    """
    await run_in_threadpool(client.remove_object, settings.minio_bucket, key)


def build_avatar_url(key: str | None) -> str | None:
    """
    Build the public URL of an avatar.

    Args:
        key (str | None): The object key stored in the profile.

    Returns:
        str | None: The URL a browser can open, or `None` if the user has no
            avatar.
    """
    if not key:
        return None
    return f"{settings.minio_public_url}/{settings.minio_bucket}/{key}"
