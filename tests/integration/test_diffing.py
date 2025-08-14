from pathlib import Path

import pytest
from dotenv import load_dotenv
from openai import Client

from breba_app.diff import apply_diff
from breba_app.generator_agent.diffing import diff_stream

load_dotenv()

client = Client()

@pytest.fixture
def html():
    path = Path(__file__).parent / "fixtures" / "diffing.html"
    return path.read_text()


@pytest.mark.asyncio
async def test_diffing(html):
    prompt = "The user has highlighted the following text on the generated page: Hello. \nAnd made the following comment: Make this smaller"

    diff = ""
    async for chunk in diff_stream(html, prompt):
        diff += chunk

    modified = apply_diff(html, diff)
    evaluation = client.responses.create(
        model="gpt-4.1-nano",
        temperature=0,
        instructions="You are evaluating correctness. Just answer the question. No comments or explanations. Just the answer.",
        input=[
            {
                "role": "user",
                "content": f"#Given the following HTML:\n{modified}\n\n"
                           f"Is the Hello smaller than the world World? Answer yes or no"
            },
        ],
    )

    assert evaluation.output_text == "yes"




