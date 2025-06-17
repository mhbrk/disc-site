from typing import Tuple

from google.cloud import storage

import logging

logger = logging.getLogger(__name__)

storage_client = storage.Client()

private_bucket = storage_client.get_bucket("breba-private")
public_bucket = storage_client.get_bucket("breba-sites")


def copy_directory(
        source_bucket_name: str,
        target_bucket_name: str,
        prefix: str,  # e.g., "some/folder/"
        target_prefix: str = None  # Optional new prefix in target
):
    source_bucket = storage_client.bucket(source_bucket_name)
    target_bucket = storage_client.bucket(target_bucket_name)

    blobs = storage_client.list_blobs(source_bucket, prefix=prefix)

    for blob in blobs:
        # Compute new destination name
        relative_path = blob.name[len(prefix):]
        new_prefix = target_prefix if target_prefix is not None else prefix
        new_name = f"{new_prefix}{relative_path}"

        # Copy blob to target
        new_blob = source_bucket.copy_blob(blob, target_bucket, new_name)
        new_blob.make_public()

        logger.info(f"Copied {blob.name} -> {new_name}")


def save_image_to_private(session_id: str, image_name: str, content: bytes, description: str = None):
    blob = private_bucket.blob(f"{session_id}/images/{image_name}")
    if description is not None:
        blob.metadata = {"description": description}
    blob.upload_from_string(content, "image/png")


def save_image_file_to_private(session_id: str, file_name: str, file_path: str, description: str = None):
    relative_path = f"images/{file_name}"
    blob = private_bucket.blob(f"{session_id}/{relative_path}")
    if description is not None:
        blob.metadata = {"description": description}
    blob.upload_from_filename(file_path)
    return relative_path


def read_image_from_private(session_id: str, image_name: str) -> Tuple[bytes, dict[str, str]] | None:
    blob = private_bucket.blob(f"{session_id}/images/{image_name}")

    if not blob.exists():
        return None

    blob.reload()
    return blob.download_as_bytes(), blob.metadata


def save_file_to_private(session_id: str, file_name: str, content: bytes, content_type: str):
    private_bucket.blob(f"{session_id}/{file_name}").upload_from_string(content, content_type)
