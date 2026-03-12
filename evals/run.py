from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from breba_app.coder_agent.agent import run_coder_agent
from breba_app.filesystem import FileWrite, in_memory_store
from evals.loader import load_messages, load_initial_files


@dataclass
class CaseResult:
    case: str
    passed: bool
    error: str | None
    agent_message: str
    initial_files: list[str]
    final_files: list[str]
    modified_files: list[str]


def compute_modified_files(before: dict[str, FileWrite], after: dict[str, FileWrite]) -> list[str]:
    modified: list[str] = []
    for path, after_content in after.items():
        before_content = before.get(path)
        if before_content is None or before_content != after_content:
            modified.append(path)
    return sorted(modified)


async def run_case(case_dir: Path) -> CaseResult:
    case_name = case_dir.name

    messages = load_messages(case_dir)
    initial = load_initial_files(case_dir)

    store = in_memory_store.from_raw_strings(initial)
    before = store.snapshot()

    try:
        agent_message = await run_coder_agent(messages=messages, filestore=store)
    except Exception as e:
        return CaseResult(
            case=case_name,
            passed=False,
            error=f"Agent crashed: {e}",
            agent_message="",
            initial_files=sorted(before.keys()),
            final_files=sorted(before.keys()),
            modified_files=[],
        )

    after = store.snapshot()
    modified = compute_modified_files(before, after)

    # For now: "passed" just means the agent did not error.
    # We will add deterministic + judge checks in the next step.
    passed = not agent_message.startswith("ERROR:")

    return CaseResult(
        case=case_name,
        passed=passed,
        error=None if passed else agent_message,
        agent_message=agent_message,
        initial_files=sorted(before.keys()),
        final_files=sorted(after.keys()),
        modified_files=modified,
    )


async def main() -> None:
    cases_root = Path(__file__).parent / "cases"
    case_dirs = sorted([p for p in cases_root.iterdir() if p.is_dir()])

    results: list[dict[str, Any]] = []
    passed = 0

    for case_dir in case_dirs:
        r = await run_case(case_dir)
        results.append(r.__dict__)
        if r.passed:
            passed += 1

    runs_dir = Path(__file__).parent / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    out_path = runs_dir / "latest.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"Passed {passed}/{len(results)}")
    for r in results:
        if not r["passed"]:
            print(f"- FAIL {r['case']}: {r['error']}")


if __name__ == "__main__":
    asyncio.run(main())
