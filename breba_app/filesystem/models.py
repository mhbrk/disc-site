from dataclasses import dataclass


@dataclass(frozen=True)
class FileWrite:
    """A single file write operation for batch_write."""
    path: str
    content: bytes | str
    content_type: str | None = None