from __future__ import annotations

from typing import Dict, List


class InMemoryFileStore:
    """
    Minimal FileStore implementation for tests:
    - paths are treated as case-sensitive POSIX-ish strings
    - all content is text (str)
    """

    def __init__(self, initial: Dict[str, str] | None = None):
        self._files: Dict[str, str] = dict(initial or {})

    def read_text(self, path: str) -> str:
        if path not in self._files:
            raise FileNotFoundError(path)
        return self._files[path]

    def write_text(self, path: str, content: str) -> None:
        self._files[path] = content

    def list_files(self) -> List[str]:
        return sorted(self._files.keys())

    def snapshot(self) -> Dict[str, str]:
        return dict(self._files)


def compute_modified_files(before: Dict[str, str], after: Dict[str, str]) -> List[str]:
    """
    "Modified" means: new file OR content changed. Deletions are ignored for now.
    """
    modified: List[str] = []
    for path, after_content in after.items():
        before_content = before.get(path, None)
        if before_content is None or before_content != after_content:
            modified.append(path)
    return sorted(modified)
