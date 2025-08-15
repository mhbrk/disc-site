from pathlib import Path

import pytest
from dotenv import load_dotenv
from openai import Client

from breba_app.diff import apply_diff_no_line_numbers
from breba_app.generator_agent.diffing import diff_text

load_dotenv()

client = Client()

EVALUATION_PROMPT = "You are evaluating correctness. Just answer the question. No comments or explanations. Just the answer."
EVALUATION_MODEL = "gpt-4.1-nano"


@pytest.fixture
def html():
    path = Path(__file__).parent / "fixtures" / "diffing.html"
    return path.read_text()


@pytest.mark.asyncio
async def test_diffing_inline_style(html):
    prompt = "The user has highlighted the following text on the generated page: Hello. \nAnd made the following comment: Make this smaller"

    diff = await diff_text(html, prompt)

    modified = apply_diff_no_line_numbers(html, diff)
    evaluation = client.responses.create(
        model=EVALUATION_MODEL,
        temperature=0,
        instructions=EVALUATION_PROMPT,
        input=[
            {
                "role": "user",
                "content": f"#Given the following HTML:\n{modified}\n\n"
                           f"Is the 'Hello' smaller than the word 'World'? Answer yes or no"
            },
        ],
    )

    assert evaluation.output_text.lower().strip() == "yes"


@pytest.mark.asyncio
async def test_diffing_inline_text(html):
    prompt = "The user has highlighted the following text on the generated page: Hello World. \nAnd made the following comment: Should be Hello, Universe!"

    diff = await diff_text(html, prompt)

    modified = apply_diff_no_line_numbers(html, diff)
    evaluation = client.responses.create(
        model=EVALUATION_MODEL,
        temperature=0,
        instructions=EVALUATION_PROMPT,
        input=[
            {
                "role": "user",
                "content": f"#Given the following HTML:\n{modified}\n\n"
                           f"Does the text say 'Hello, Universe!' and not 'Hello World'? Answer yes or no"
            },
        ],
    )

    assert evaluation.output_text.lower().strip() == "yes"
