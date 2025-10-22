from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import posixpath
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Dict, Any

from botocore.client import BaseClient
from botocore.exceptions import ClientError


@dataclass(frozen=True)
class FileWrite:
    """A single file write operation for batch_write."""
    path: str
    content: bytes | str
    content_type: str | None = None


@dataclass
class FileMetadata:
    """Metadata for a file in a version."""
    path: str
    key: str
    sha256: str
    size: int
    content_type: str
    version: int


class VersionedFileSystemError(Exception):
    pass


class NotFound(VersionedFileSystemError):
    pass


class VersionedR2FileSystem:
    """
    A versioned file system abstraction backed by Cloudflare R2 (S3-compatible).

    Features:
    - Manifest-based versioning (copy-on-write)
    - Deduplication of unchanged files
    - Optional content-addressed storage (CAS)
    - Safe path handling and clean API
    """

    def __init__(
            self,
            *,
            bucket_name: str,
            root_prefix: str,
            s3_client: BaseClient,
            use_content_addressed_storage: bool = False,
    ) -> None:
        if not bucket_name:
            raise ValueError("bucket_name is required")
        if not s3_client:
            raise ValueError("s3_client is required")
        if not root_prefix:
            raise ValueError("root_prefix are required")

        self._bucket = bucket_name
        self._prefix = root_prefix
        self._s3 = s3_client
        self._use_cas = use_content_addressed_storage

    # ----------------------------- Public API ----------------------------- #

    def get_version(self) -> int:
        """Return the currently selected (latest) version integer."""
        try:
            obj = self._s3.get_object(Bucket=self._bucket, Key=self._latest_key())
            body = obj["Body"].read().decode("utf-8").strip()
            return int(body)
        except (ClientError, self._s3.exceptions.NoSuchKey):
            self._init_version_zero()
            return 0

    def set_version(self, version: int) -> None:
        """Move the pointer to a specific version (rollback/roll-forward)."""
        if version < 0:
            raise ValueError("version must be >= 0")
        if not self._object_exists(self._manifest_key(version)):
            raise NotFound(f"Version {version} does not exist")
        self._put_text(self._latest_key(), str(version))

    def list_files(self, version: int | None = None, prefix: str = "") -> List[str]:
        """List all logical file paths in the given version."""
        v = self.get_version() if version is None else version
        manifest = self._get_manifest(v)
        return sorted(p for p in manifest["files"].keys() if p.startswith(prefix))

    def file_exists(self, path: str, version: int | None = None) -> bool:
        """Check if a file exists in the given version."""
        try:
            v = self.get_version() if version is None else version
            manifest = self._get_manifest(v)
            return _sanitize_path(path) in manifest["files"]
        except (NotFound, ClientError):
            return False

    async def read_file(self, path: str, *, version: int | None = None) -> bytes:
        """Read file bytes from the given version."""
        sanitized_path = _sanitize_path(path)

        def _sync_read():
            resolved_version = self.get_version() if version is None else version
            if resolved_version > 0:
                manifest = self._get_manifest(resolved_version)
                meta = manifest["files"].get(sanitized_path)
                if not meta:
                    raise NotFound(f"{sanitized_path} not found in version {resolved_version}")
                key = meta["key"]
            else:
                # If version is 0 or None, we are reading the unversioned copy
                key = self._prefix + "/" + sanitized_path
            try:
                obj = self._s3.get_object(Bucket=self._bucket, Key=key)
                return obj["Body"].read()
            except (ClientError, self._s3.exceptions.NoSuchKey):
                raise NotFound(f"Object for {sanitized_path} not found (key={key})")

        return await asyncio.to_thread(_sync_read)

    async def read_text(self, path: str, *, version: int | None = None, encoding: str = "utf-8") -> str:
        """Read file content as text."""
        return (await self.read_file(path, version=version)).decode(encoding)

    def write_file(self, path: str, content: bytes | str, *, content_type: str | None = None) -> int:
        """Write a single file and create a new version."""
        return self.batch_write([FileWrite(path=path, content=content, content_type=content_type)])

    def batch_write(self, files: Iterable[FileWrite]) -> int:
        """Atomically write a batch of files and create one new version."""
        files = list(files)
        if not files:
            raise ValueError("batch_write requires at least one FileWrite")

        base_version = self.get_version()
        new_version = base_version + 1
        base_manifest = self._get_manifest(base_version)
        new_manifest = {
            "version": new_version,
            "parent": base_version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "files": dict(base_manifest["files"]),
        }

        for fw in files:
            path = _sanitize_path(fw.path)
            data = fw.content.encode("utf-8") if isinstance(fw.content, str) else fw.content
            ctype = fw.content_type or _guess_content_type(path)
            sha = hashlib.sha256(data).hexdigest()

            old_meta = base_manifest["files"].get(path)
            if old_meta and old_meta["sha256"] == sha:
                new_manifest["files"][path] = old_meta
                continue

            if self._use_cas:
                key = self._content_addressed_key(sha)
                if not self._object_exists(key):
                    self._s3.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=ctype)
            else:
                key = self._versioned_file_key(new_version, path)
                self._s3.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=ctype)

            new_manifest["files"][path] = {
                "key": key,
                "sha256": sha,
                "size": len(data),
                "content_type": ctype,
            }

        self._put_json(self._manifest_key(new_version), new_manifest)
        self._put_text(self._latest_key(), str(new_version))
        return new_version

    # ------------------------- Private helpers ---------------------------- #

    def _init_version_zero(self) -> None:
        """Initialize version 0 manifest if missing."""
        key = self._manifest_key(0)
        if not self._object_exists(key):
            self._put_json(
                key,
                {
                    "version": 0,
                    "parent": None,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "files": {},
                },
            )
        self._put_text(self._latest_key(), "0")

    def _get_manifest(self, version: int) -> Dict[str, Any]:
        try:
            obj = self._s3.get_object(Bucket=self._bucket, Key=self._manifest_key(version))
            return json.loads(obj["Body"].read().decode("utf-8"))
        except (ClientError, self._s3.exceptions.NoSuchKey):
            raise NotFound(f"Version {version} does not exist")

    def _object_exists(self, key: str) -> bool:
        """Return True only for 404-like errors; re-raise others."""
        try:
            self._s3.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def _put_text(self, key: str, text: str) -> None:
        self._s3.put_object(
            Bucket=self._bucket, Key=key, Body=text.encode("utf-8"), ContentType="text/plain"
        )

    def _put_json(self, key: str, obj: Dict[str, Any]) -> None:
        self._s3.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )

    def _latest_key(self) -> str:
        return f"{self._prefix}/manifests/LATEST"

    def _manifest_key(self, version: int) -> str:
        return f"{self._prefix}/manifests/{version}.json"

    def _versioned_file_key(self, version: int, logical_path: str) -> str:
        logical_path = logical_path.lstrip("/")
        return f"{self._prefix}/versions/{version}/{logical_path}"

    def _content_addressed_key(self, sha256: str) -> str:
        return f"{self._prefix}/objects/{sha256[:2]}/{sha256}"

    def __repr__(self) -> str:
        """Do not perform network I/O in repr."""
        return f"VersionedR2FileSystem(prefix='{self._prefix}', bucket='{self._bucket}')"


# --------------------------- Helper functions ----------------------------- #

def _guess_content_type(path: str) -> str:
    ctype, _ = mimetypes.guess_type(path)
    return ctype or "application/octet-stream"


def _clean(part: str) -> str:
    s = part.strip().lower()
    return "".join(ch for ch in s if ch.isalnum() or ch in ("-", "_"))


def _sanitize_path(p: str) -> str:
    """Reject traversal and control chars; normalize slashes."""
    if not p or p.endswith("/"):
        raise ValueError("path must be a file path (not a directory)")
    p = p.replace("\\", "/")
    if re.search(r"[\x00-\x1f]", p):
        raise ValueError("path contains control characters")
    parts = []
    for seg in p.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            raise ValueError("path traversal not allowed")
        parts.append(seg)
    return posixpath.join(*parts)
