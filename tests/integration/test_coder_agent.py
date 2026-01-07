from __future__ import annotations

from pathlib import Path
import pytest

from .conftest import InMemoryFileStore, compute_modified_files
import breba_app.coder_agent.agent as agent_mod


def load_dir_texts(dir_path: Path) -> dict[str, str]:
    if not dir_path.exists():
        return {}
    out: dict[str, str] = {}
    for p in dir_path.rglob("*"):
        if p.is_file():
            rel = p.relative_to(dir_path).as_posix()
            out[rel] = p.read_text(encoding="utf-8")
    return out


def load_case(case_dir: Path) -> tuple[dict[str, str], str, dict[str, str]]:
    initial = load_dir_texts(case_dir / "initial")
    llm_output = (case_dir / "llm_output.txt").read_text(encoding="utf-8")
    expected = load_dir_texts(case_dir / "expected")
    return initial, llm_output, expected


def assert_expected_files_match(store: InMemoryFileStore, expected: dict[str, str]) -> None:
    for path, expected_content in expected.items():
        actual = store.read_text(path)
        assert actual == expected_content, f"Mismatch in {path}"


@pytest.mark.parametrize("case_name, expected_modified", [
    ("hello_world_create", ["index.html", "styles.css", "scripts.js", "sitemap.xml", "robots.txt"]),
    ("modify_text", ["index.html", "sitemap.xml"]),
])
@pytest.mark.asyncio
async def test_agent_case_snapshots(monkeypatch, case_name: str, expected_modified: list[str]) -> None:
    case_dir = Path(__file__).parent / "coder_agent_test_cases" / case_name
    initial, llm_output, expected = load_case(case_dir)

    store = InMemoryFileStore(initial)
    before = store.snapshot()

    async def fake_generate_search_replace_blocks(messages):
        return llm_output

    # If the import of b failed in the agent module for any reason,
    # create a dummy so we can still patch the attribute.
    if getattr(agent_mod, "b", None) is None:
        class DummyB: ...
        agent_mod.b = DummyB()

    monkeypatch.setattr(agent_mod.b, "GenerateSearchReplaceBlocks", fake_generate_search_replace_blocks)

    result_msg = await agent_mod.run_coder_agent(
        messages=[{"role": "user", "content": f"case={case_name}"}],
        filestore=store,
    )
    assert isinstance(result_msg, str)
    assert not result_msg.startswith("ERROR:"), result_msg

    after = store.snapshot()
    modified = compute_modified_files(before, after)

    # Strict modified set
    assert modified == sorted(expected_modified)

    # Exact content checks
    assert_expected_files_match(store, expected)

    # Sanity: returned message should mention modified files
    for p in expected_modified:
        assert p in result_msg
