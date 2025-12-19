from pathlib import Path

import pytest

from breba_app.generator_agent.diffing import apply_search_replace
from breba_app.search_replace_editing import HEAD_ERR, UPDATED_ERR, DIVIDER_ERR


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    # Adjust if your tests live elsewhere
    return Path(__file__).parent / "fixtures"


def read_text_normalized(p: Path) -> str:
    # Normalize to LF regardless of file's native line endings
    return "\n".join(p.read_text().splitlines()) + "\n"  # Also add new line at the end because splitlines removes it


@pytest.fixture(scope="session")
def original_html_two_sections(fixtures_dir) -> str:
    return read_text_normalized(fixtures_dir / "original_two_sections.html")


@pytest.fixture(scope="session")
def modified_html_two_sections(fixtures_dir) -> str:
    return read_text_normalized(fixtures_dir / "modified_two_sections.html")


@pytest.fixture
def diff_with_two_sections(fixtures_dir):
    return read_text_normalized(fixtures_dir / "search_replace_two_sections.txt")


@pytest.fixture
def invalid_diff():
    return "--- invalid diff ---"


def test_apply_diff_with_two_sections(original_html_two_sections, modified_html_two_sections, diff_with_two_sections):
    result = apply_search_replace(original_html_two_sections, diff_with_two_sections)
    assert result == modified_html_two_sections

def test_apply_no_edits_found(original_html_two_sections):
    result = apply_search_replace(original_html_two_sections, f"index.html\n```html"
                                                                      f"\n{HEAD_ERR}"
                                                                      f"\nABCDEFG"
                                                                      f"\n{DIVIDER_ERR}"
                                                                      f"\nXYZ"
                                                                      f"\n{UPDATED_ERR}\n```")
    assert result == original_html_two_sections

def test_apply_invalid_diff(original_html_two_sections, invalid_diff):
    with pytest.raises(ValueError):
        apply_search_replace(original_html_two_sections, invalid_diff)