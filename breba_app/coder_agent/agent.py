from __future__ import annotations

from typing import Any, Protocol

from breba_app.coder_agent.baml_client.async_client import b  # type: ignore
from breba_app.coder_agent.baml_client.types import LLMMessage
from breba_app.search_replace_editing import apply_search_replace_many

NO_FILES_TO_MODIFY_MSG = "No files to modify for this request"


class FileStore(Protocol):
    def read_text(self, path: str) -> str: ...

    def write_text(self, path: str, content: str) -> None: ...

    def list_files(self) -> list[str]: ...

    def file_exists(self, path: str) -> bool: ...


def _snapshot(fs: FileStore) -> dict[str, str]:
    return {p: fs.read_text(p) for p in fs.list_files()}


def _modified_files(before: dict[str, str], after: dict[str, str]) -> list[str]:
    out: list[str] = []
    for path, after_content in after.items():
        before_content = before.get(path)
        if before_content is None or before_content != after_content:
            out.append(path)
    return sorted(out)


def _render_file(file_name: str, file_content: str):
    return f"""{file_name}
```
{file_content}
```
"""


async def read_files_to_edit(*, original_context: list[LLMMessage], filestore: FileStore):
    max_depth = 5
    files_list = filestore.list_files()
    if not files_list:
        # This indicates that we just don't have file.
        return ""
    file_list_msg = f"\n\n<available_files_list>\n{",".join(files_list)}\n<available_files_list>"

    safe_context = original_context.copy()
    response = ""
    # append the files list to the last user message.
    safe_context[-1] = LLMMessage(role=safe_context[-1].role, content=safe_context[-1].content + file_list_msg)

    seen_files = set()
    while True:
        # Prevent infinite loop
        max_depth -= 1
        if max_depth == 0:
            break

        files_response = await b.DetermineFilesToEdit(safe_context)

        if not files_response.files:
            # There are no new files to read for this task
            break

        files_response_set = set(files_response.files)

        new_files_set = files_response_set - seen_files

        if new_files_set:
            seen_files = seen_files | new_files_set
            for file_name in new_files_set:
                if not filestore.file_exists(file_name):
                    continue
                file_content = filestore.read_text(file_name)
                response += _render_file(file_name, file_content)
        else:
            # The new files are already in the list, no new files to add to the context
            break

        safe_context.append(LLMMessage(role="assistant", content=response))

        follow_up_msg = (f"Here are the file contents of the files:\n"
                         f"{response}\n"
                         f"Are additional files needed to satisfy?\n")
        safe_context.append(LLMMessage(role="assistant", content=follow_up_msg))

    # If no files ot modify maybe need a reason?
    return response or NO_FILES_TO_MODIFY_MSG


async def run_coder_agent(*, messages: list[Any], filestore: FileStore) -> LLMMessage:
    """
    Stateless agent.
    Success: returns a string listing updated files.
    Failure: returns an error string.
    """
    safe_context = messages.copy()

    files_to_edit = await read_files_to_edit(original_context=messages, filestore=filestore)
    files_to_edit_msg = (f"\n\nThe following files are available for editing. Do not edit any other files.\n"
                         f"<files_available_for_editing>\n{files_to_edit}\n</files_available_for_editing>")
    # We will just inject files context into the last message...
    safe_context[-1] = LLMMessage(role=safe_context[-1].role, content=safe_context[-1].content + files_to_edit_msg)

    try:
        search_replace_text = await b.GenerateSearchReplaceBlocks(safe_context)  # type: ignore[attr-defined]
    except Exception as e:
        return LLMMessage(role="assistant", content=f"ERROR: BAML call failed: {e}")

    files = _snapshot(filestore)
    before = dict(files)

    try:
        # TODO: add retry logic
        edits = apply_search_replace_many(files, search_replace_text)
    except Exception as e:
        # Atomic behavior: do not write anything on failure
        return LLMMessage(role="assistant", content=f"ERROR: {e}")

    modified = _modified_files(before, files)

    # Write back only changed/new files
    for path in modified:
        filestore.write_text(path, files[path])

    if not modified:
        return LLMMessage(role="assistant", content="UPDATED_FILES:\n(none)")

    return LLMMessage(role="assistant", content="UPDATED_FILES:\n" + "\n".join(f"- {p}" for p in modified))
