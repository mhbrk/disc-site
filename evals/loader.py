from __future__ import annotations

import json
from pathlib import Path

from breba_app.coder_agent.baml_client.stream_types import LLMMessage


def load_messages(case_dir: Path) -> list[LLMMessage]:
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    return [LLMMessage.model_validate(message) for message in case["messages"]]


def load_dir_texts(dir_path: Path) -> dict[str, str]:
    if not dir_path.exists():
        return {}
    out: dict[str, str] = {}
    for p in dir_path.rglob("*"):
        if p.is_file():
            rel = p.relative_to(dir_path).as_posix()
            out[rel] = p.read_text(encoding="utf-8")
    return out


def load_initial_files(case_dir: Path) -> dict[str, str]:
    # Mirror integration test convention
    return load_dir_texts(case_dir / "initial")


def load_evals(case_dir: Path) -> dict:
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    return case["evals"]
