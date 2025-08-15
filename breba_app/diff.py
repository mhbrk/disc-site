import difflib


class PatchApplyError(Exception):
    pass


def get_diff(old_text: str, new_text: str):
    diff = difflib.unified_diff(
        old_text.splitlines(),
        new_text.splitlines(),
        fromfile='before',
        tofile='after',
        lineterm=''
    )
    return "\n".join(diff) + "\n"


def validate_diff(diff_text: str):
    """Validate that the diff has proper format"""
    lines = diff_text.splitlines()

    if not lines:
        raise PatchApplyError("Empty diff")

    # Check for required headers
    has_minus_header = False
    has_plus_header = False
    has_hunk_header = False

    for line in lines:
        if line.startswith("--- "):
            has_minus_header = True
        elif line.startswith("+++ "):
            has_plus_header = True
        elif line.startswith("@@"):
            has_hunk_header = True
            break  # We found at least one hunk header

    if not has_minus_header:
        raise PatchApplyError("Missing '--- ' header line")
    if not has_plus_header:
        raise PatchApplyError("Missing '+++ ' header line")
    if not has_hunk_header:
        raise PatchApplyError("Missing '@@ ... @@' hunk header")

    # Validate hunk content
    in_hunk = False
    hunk_has_content = False

    for line in lines:
        if line.startswith("@@"):
            if in_hunk and not hunk_has_content:
                raise PatchApplyError("Empty hunk found")
            in_hunk = True
            hunk_has_content = False
            continue

        if not in_hunk:
            continue

        if line and line[0] in " -+":
            hunk_has_content = True
        elif line.strip() == "":
            # Empty lines are OK
            continue
        else:
            # Invalid line in hunk
            raise PatchApplyError(f"Invalid line in hunk: {line!r}")


def apply_diff_no_line_numbers(original_text: str, diff_text: str) -> str:
    validate_diff(diff_text)
    original_lines = original_text.splitlines(keepends=True)

    # Parse hunks
    hunks = parse_hunks(diff_text)

    # Apply hunks in reverse order to avoid index shifting
    result_lines = list(original_lines)

    for hunk in reversed(hunks):
        result_lines = apply_hunk(result_lines, hunk)

    return ''.join(result_lines)


def parse_hunks(diff_text: str):
    """Parse diff into individual hunks"""
    hunks = []
    current_hunk = []
    in_hunk = False

    for line in diff_text.splitlines(keepends=True):
        if line.startswith("@@"):
            if current_hunk:  # save previous hunk
                hunks.append(current_hunk)
            current_hunk = []
            in_hunk = True
            continue

        if not in_hunk:
            continue

        if line.startswith((" ", "-", "+")):
            current_hunk.append(line)
        else:
            # End of hunk (or invalid line)
            if current_hunk:
                hunks.append(current_hunk)
                current_hunk = []
            in_hunk = False

    # Don't forget the last hunk
    if current_hunk:
        hunks.append(current_hunk)

    return hunks


def find_hunk_start(original_lines, hunk_lines):
    """Find the starting line index for a hunk by matching all removed lines"""
    # Extract all removed lines (and context lines) to match against
    lines_to_match = []
    for line in hunk_lines:
        if line.startswith(" ") or line.startswith("-"):
            lines_to_match.append(line[1:])  # remove the prefix

    if not lines_to_match:
        raise PatchApplyError(f"Hunk has no context or removed lines to match against: {hunk_lines}")

    # Find where this sequence appears in the original
    for i in range(len(original_lines) - len(lines_to_match) + 1):
        if original_lines[i:i + len(lines_to_match)] == lines_to_match:
            return i

    raise PatchApplyError(f"Could not find matching sequence in original file.\n"
                          f"Looking for: {lines_to_match}")


def apply_hunk(original_lines, hunk_lines):
    """Apply a single hunk to the original lines"""
    start_idx = find_hunk_start(original_lines, hunk_lines)

    # Build the replacement content
    new_content = []
    original_idx = start_idx

    for line in hunk_lines:
        if line.startswith(" "):  # context
            new_content.append(line[1:])
            original_idx += 1
        elif line.startswith("-"):  # removal
            # Skip this line (don't add to new_content)
            original_idx += 1
        elif line.startswith("+"):  # addition
            new_content.append(line[1:])
        else:
            raise PatchApplyError(f"Unexpected line in diff: {line!r}")

    # Calculate how many lines we're replacing
    lines_consumed = original_idx - start_idx

    # Replace the section
    result_lines = (
            original_lines[:start_idx] +
            new_content +
            original_lines[start_idx + lines_consumed:]
    )

    return result_lines
