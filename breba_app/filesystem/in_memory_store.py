import mimetypes
from typing import Protocol

from breba_app.filesystem.models import FileWrite


class FileStore(Protocol):
    def read_text(self, path: str) -> str: ...

    def write_text(self, path: str, content: str) -> None: ...

    def list_files(self) -> list[str]: ...

    def file_exists(self, path: str) -> bool: ...


class InMemoryFileStore(FileStore):
    """
    Minimal FileStore implementation for tests:
    - paths are treated as case-sensitive POSIX-ish strings
    - all content is text (str)
    """

    def __init__(self, initial: dict[str, FileWrite] | None = None):
        self._files: dict[str, FileWrite] = dict(initial or {})

    def read_text(self, path: str) -> str:
        if path not in self._files:
            raise FileNotFoundError(path)
        return self._files[path].content.decode("utf-8")

    def write_text(self, path: str, content: str) -> None:
        content_type, encoding = mimetypes.guess_type(path)
        self._files[path] = FileWrite(path, content.encode("utf-8"), content_type)

    def list_files(self) -> list[str]:
        return sorted(self._files.keys())

    def file_exists(self, path: str) -> bool:
        return path in self._files

    def snapshot(self) -> dict[str, FileWrite]:
        return dict(self._files)
