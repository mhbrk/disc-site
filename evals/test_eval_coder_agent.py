from __future__ import annotations

from pathlib import Path

import pytest
from dotenv import load_dotenv
from openai import Client

from breba_app.coder_agent.agent import run_coder_agent, FileStore
from breba_app.coder_agent.baml_client.types import LLMMessage
from breba_app.filesystem import InMemoryFileStore
from evals.loader import load_messages, load_initial_files, load_evals

load_dotenv()

client = Client()

EVALUATION_PROMPT = "You are evaluating correctness. Just answer the question. No comments or explanations. Just the answer."
EVALUATION_MODEL = "gpt-5-nano"


def _render_file(file_name: str, file_content: str):
    return f"""{file_name}
```
{file_content}
```
"""


def load_case(case_dir: Path) -> tuple[list[LLMMessage], FileStore]:
    raw_messages = load_messages(case_dir)
    messages = [LLMMessage.model_validate(message) for message in raw_messages]

    initial = load_initial_files(case_dir)

    store = InMemoryFileStore(initial)
    return (messages, store)


async def run_evals(case_dir: Path, text: str):
    evals = load_evals(case_dir)
    for evaluation in evals["evals"]:
        eval_message_content = (f"#Given the following text:\n{text}\n\n"
                                f"{evaluation["question"]}\n"
                                f"Your allowed answer options: {evaluation.get("answer_options", "answer options are not restricted")}\n")
        result = client.responses.create(
            model=EVALUATION_MODEL,
            reasoning={"effort": "minimal"},
            text={"verbosity": "low"},
            input=[
                {
                    "role": "system",
                    "content": EVALUATION_PROMPT
                },
                {
                    "role": "user",
                    "content": eval_message_content
                }
            ])
        print(eval_message_content)
        assert result.output_text.lower().strip() == evaluation["expected_answer"]


@pytest.mark.asyncio
async def test_coder_create_new_website() -> None:
    case_dir = Path(__file__).parent / "cases" / "create_hello_world"

    messages, store = load_case(case_dir)
    files_content = ""
    agent_response = await run_coder_agent(messages=messages, filestore=store)
    for file_name in store.list_files():
        file_content = store.read_text(file_name)
        files_content += _render_file(file_name, file_content)
    # Combine side effect changes to the files with the agent message
    combined_agent_response = f"{agent_response.content}\n\nThe following are the resulting files form the agent work:\n{files_content}"
    await run_evals(case_dir, combined_agent_response)

    # runs_dir = Path(__file__).parent / "runs"
    # runs_dir.mkdir(parents=True, exist_ok=True)
    # out_path = runs_dir / "latest.json"
    # out_path.write_text(json.dumps(r.__dict__, indent=2), encoding="utf-8")
