from __future__ import annotations


def compute_modified_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """
    "Modified" means: new file OR content changed. Deletions are ignored for now.
    """
    modified: list[str] = []
    for path, after_content in after.items():
        before_content = before.get(path, None)
        if before_content is None or before_content != after_content:
            modified.append(path)
    return sorted(modified)
