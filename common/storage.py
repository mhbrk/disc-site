from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Tuple, TypedDict, Union

from dotenv import load_dotenv
from google.cloud import storage
from google.cloud.storage import Bucket

load_dotenv()

logger = logging.getLogger(__name__)

storage_client = storage.Client()

private_bucket: Bucket = storage_client.get_bucket(os.getenv("USERS_BUCKET"))
public_bucket: Bucket = storage_client.get_bucket(os.getenv("PUBLIC_BUCKET"))


class FileMetadata(TypedDict):
    description: str  # No need for __description__


DirTreeValue = Union[FileMetadata, "DirTree"]
DirTree = dict[str, DirTreeValue]


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


def make_dir_tree() -> DirTree:
    return defaultdict(make_dir_tree)


def register_file(parts: list[str], tree: DirTree):
    current = tree
    for part in parts[:-1]:
        current = current[part]
    return current


def list_files_structured(session_id: str) -> DirTree:
    blobs = private_bucket.list_blobs(prefix=f"{session_id}")
    files = make_dir_tree()

    for blob in blobs:
        parts = blob.name[len(session_id) + 1:].split("/")  # skip session_id prefix
        file_name = parts[-1]

        file = register_file(parts, files)
        if blob.metadata:
            file[file_name] = {
                "__description__": blob.metadata.get("description", "No description")
            }
        else:
            file[file_name] = {"__description__": "No description"}

    return files


def format_tree(tree: DirTree, indent=0):
    lines = []
    for key, value in sorted(tree.items()):
        if isinstance(value, dict) and "__description__" in value:
            desc = value["__description__"]
            lines.append("  " * indent + f"- {key} ({desc})")
        else:
            lines.append("  " * indent + f"{key}/")
            lines.extend(format_tree(value, indent + 1))
    return lines


def list_files_in_private(session_id: str):
    structured = list_files_structured(session_id)
    return "\n".join(format_tree(structured))


def upload_site(session_id: str, site_name: str):
    """
    Uploads site to google cloud
    Example: upload_site("/Users/yason/breba/disc-site/sites/test-site", "test-site")
    :param session_id: session id used for locating site files
    :param site_name: site name where all the files will be stored
    :return:
    """
    copy_directory(
        source_bucket_name=private_bucket.name,
        target_bucket_name=public_bucket.name, prefix=session_id, target_prefix=site_name
    )

    url = f"https://storage.googleapis.com/{public_bucket.name}/{site_name}/index.html"
    return url