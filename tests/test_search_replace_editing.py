from pathlib import Path

import pytest

from breba_app.generator_agent.diffing import apply_search_replace_to_html


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


def test_apply_diff_with_two_sections(original_html_two_sections, modified_html_two_sections, diff_with_two_sections):
    result = apply_search_replace_to_html(original_html_two_sections, diff_with_two_sections)
    assert result == modified_html_two_sections
