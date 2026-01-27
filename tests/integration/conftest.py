from __future__ import annotations

from breba_app.filesystem import FileWrite


def compute_modified_files(before: dict[str, FileWrite], after: dict[str, FileWrite]) -> list[str]:
    """
    "Modified" means: new file OR content changed. Deletions are ignored for now.
    """
    modified: list[str] = []
    for path, after_content in after.items():
        before_content = before.get(path, None)
        if before_content is None or before_content.content != after_content.content:
            modified.append(path)
    return sorted(modified)
