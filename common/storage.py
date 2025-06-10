from google.cloud import storage

import logging

logger = logging.getLogger(__name__)

def copy_directory(
    source_bucket_name: str,
    target_bucket_name: str,
    prefix: str,  # e.g., "some/folder/"
    target_prefix: str = None  # Optional new prefix in target
):
    storage_client = storage.Client()

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


def save_image_to_private(session_id: str, image_name: str, content: bytes,):
    storage_client = storage.Client()
    bucket = storage_client.get_bucket("breba-private")

    bucket.blob(f"{session_id}/images/{image_name}").upload_from_string(content, "image/png")


def save_file_to_private(session_id: str, file_name: str, content: bytes, content_type: str):
    storage_client = storage.Client()
    bucket = storage_client.get_bucket("breba-private")

    bucket.blob(f"{session_id}/{file_name}").upload_from_string(content, content_type)

