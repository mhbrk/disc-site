from __future__ import annotations

from typing import Any, Protocol


from breba_app.coder_agent.baml_client.async_client import b  # type: ignore
from breba_app.search_replace_editing import apply_search_replace_many


class FileStore(Protocol):
    def read_text(self, path: str) -> str: ...
    def write_text(self, path: str, content: str) -> None: ...
    def list_files(self) -> list[str]: ...


def _snapshot(fs: FileStore) -> dict[str, str]:
    return {p: fs.read_text(p) for p in fs.list_files()}


def _modified_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    out: list[str] = []
    for path, after_content in after.items():
        before_content = before.get(path)
        if before_content is None or before_content != after_content:
            out.append(path)
    return sorted(out)


async def run_coder_agent(*, messages: list[Any], filestore: FileStore) -> str:
    """
    Stateless agent.
    Success: returns a string listing updated files.
    Failure: returns an error string.
    """
    try:
        search_replace_text = await b.GenerateSearchReplaceBlocks(messages)  # type: ignore[attr-defined]
    except Exception as e:
        return f"ERROR: BAML call failed: {e}"

    files = _snapshot(filestore)
    before = dict(files)

    try:
        edits = apply_search_replace_many(files, search_replace_text)
    except Exception as e:
        # Atomic behavior: do not write anything on failure
        return f"ERROR: {e}"

    modified = _modified_files(before, files)

    # Write back only changed/new files
    for path in modified:
        filestore.write_text(path, files[path])

    if not modified:
        return "UPDATED_FILES:\n(none)"

    return "UPDATED_FILES:\n" + "\n".join(f"- {p}" for p in modified)
