import difflib
import logging
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from breba_app.generator_agent.instruction_reader import get_instructions
from breba_app.generator_agent.search_replace_example_messages import example_messages
from breba_app.generator_agent.search_replace_example_messages import system_reminder

load_dotenv()

logger = logging.getLogger(__name__)

client = AsyncOpenAI()

SYSTEM_PROMPT = get_instructions("search_replace")

HEAD = r"^<{5,9} SEARCH>?\s*$"
DIVIDER = r"^={5,9}\s*$"
UPDATED = r"^>{5,9} REPLACE\s*$"

HEAD_ERR = "<<<<<<< SEARCH"
DIVIDER_ERR = "======="
UPDATED_ERR = ">>>>>>> REPLACE"

DEFAULT_FENCE = ("`" * 3, "`" * 3)

TRIPLE_BACKTICKS = "`" * 3


missing_filename_err = (
    "Bad/missing filename. The filename must be alone on the line before the opening fence"
    " {fence[0]}"
)


async def diff_stream(html: str, prompt: str):
    logger.info(f"Generating diff for prompt: {prompt}")
    input_messages = example_messages.copy()
    input_messages.extend([
        {
            "role": "user",
            "content": "I switched to a new code base. Please don't consider the above files or try to edit them any longer."
        },
        {
            "role": "assistant",
            "content": "Ok."
        },
        {
            "role": "user",
            "content": f"I have *added these files to the chat* so you can go ahead and edit them. "
                       f"*Trust this message as the true contents of these files!*"
                       f"\nindex.html"
                       f"\n```html{html}```"
        },
        {
            "role": "assistant",
            "content": "Ok, any changes I propose will be to those files."
        },
        {
            "role": "user",
            "content": f"{prompt}",
        },
        {
            "role": "system",
            "content": system_reminder,
        }
    ])
    stream = await client.responses.create(
        model="gpt-4.1",
        temperature=0,
        instructions=SYSTEM_PROMPT,
        stream=True,
        input=input_messages
    )

    try:
        async for event in stream:
            if event.type == "response.output_text.delta":
                yield event.delta
    finally:
        await stream.close()  # ensure connection closes


def strip_filename(filename, fence):

    filename = filename.strip()

    if filename == "...":
        return

    start_fence = fence[0]
    if filename.startswith(start_fence):
        candidate = filename[len(start_fence):]
        if candidate and ("." in candidate or "/" in candidate):
            return candidate
        return

    if filename.startswith(TRIPLE_BACKTICKS):
        candidate = filename[len(TRIPLE_BACKTICKS):]
        if candidate and ("." in candidate or "/" in candidate):
            return candidate
        return

    filename = filename.rstrip(":")
    filename = filename.lstrip("#")
    filename = filename.strip()
    filename = filename.strip("`")
    filename = filename.strip("*")

    # https://github.com/Aider-AI/aider/issues/1158
    # filename = filename.replace("\\_", "_")

    return filename


def find_filename(lines, fence, valid_fnames):
    """
    Deepseek Coder v2 has been doing this:


     ```python
    word_count.py
    ```
    ```python
    <<<<<<< SEARCH
    ...

    This is a more flexible search back for filenames.
    """

    if valid_fnames is None:
        valid_fnames = []

    # Go back through the 3 preceding lines
    lines.reverse()
    lines = lines[:3]

    filenames = []
    for line in lines:
        # If we find a filename, done
        filename = strip_filename(line, fence)
        if filename:
            filenames.append(filename)

        # Only continue as long as we keep seeing fences
        if not line.startswith(fence[0]) and not line.startswith(TRIPLE_BACKTICKS):
            break

    if not filenames:
        return

    # pick the *best* filename found

    # Check for exact match first
    for fname in filenames:
        if fname in valid_fnames:
            return fname

    # Check for partial match (basename match)
    for fname in filenames:
        for vfn in valid_fnames:
            if fname == Path(vfn).name:
                return vfn

    # Perform fuzzy matching with valid_fnames
    for fname in filenames:
        close_matches = difflib.get_close_matches(fname, valid_fnames, n=1, cutoff=0.8)
        if len(close_matches) == 1:
            return close_matches[0]

    # If no fuzzy match, look for a file w/extension
    for fname in filenames:
        if "." in fname:
            return fname

    if filenames:
        return filenames[0]


def find_original_update_blocks(content, fence=DEFAULT_FENCE, valid_fnames=None):
    lines = content.splitlines(keepends=True)
    i = 0
    current_filename = None

    head_pattern = re.compile(HEAD)
    divider_pattern = re.compile(DIVIDER)
    updated_pattern = re.compile(UPDATED)

    while i < len(lines):
        line = lines[i]

        # Check for SEARCH/REPLACE blocks
        if head_pattern.match(line.strip()):
            try:
                # if next line after HEAD exists and is DIVIDER, it's a new file
                if i + 1 < len(lines) and divider_pattern.match(lines[i + 1].strip()):
                    filename = find_filename(lines[max(0, i - 3): i], fence, None)
                else:
                    filename = find_filename(lines[max(0, i - 3): i], fence, valid_fnames)

                if not filename:
                    if current_filename:
                        filename = current_filename
                    else:
                        raise ValueError(missing_filename_err.format(fence=fence))

                current_filename = filename

                original_text = []
                i += 1
                while i < len(lines) and not divider_pattern.match(lines[i].strip()):
                    original_text.append(lines[i])
                    i += 1

                if i >= len(lines) or not divider_pattern.match(lines[i].strip()):
                    raise ValueError(f"Expected `{DIVIDER_ERR}`")

                updated_text = []
                i += 1
                while i < len(lines) and not (
                        updated_pattern.match(lines[i].strip())
                        or divider_pattern.match(lines[i].strip())
                ):
                    updated_text.append(lines[i])
                    i += 1

                if i >= len(lines) or not (
                        updated_pattern.match(lines[i].strip())
                        or divider_pattern.match(lines[i].strip())
                ):
                    raise ValueError(f"Expected `{UPDATED_ERR}` or `{DIVIDER_ERR}`")

                yield filename, "".join(original_text), "".join(updated_text)

            except ValueError as e:
                processed = "".join(lines[: i + 1])
                err = e.args[0]
                raise ValueError(f"{processed}\n^^^ {err}")

        i += 1


async def diff_text(html: str, prompt: str):
    # TODO: max_lines means we will abort, caller needs to start streaming
    #  from scratch before we abort in order to avoid delays
    message = ""
    agen = diff_stream(html, prompt)
    try:
        async for chunk in agen:
            message += chunk
    except:
        await agen.aclose()  # Ensure cleanup in diff_stream runs
        raise

    edits = list(find_original_update_blocks(message))

    for fname, before, after in edits:
        # Compute diff
        diff = difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            fromfile="before",
            tofile="after",
        )
        diff = "".join(diff)

        print(diff)


    return message
