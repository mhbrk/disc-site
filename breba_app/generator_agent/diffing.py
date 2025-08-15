from dotenv import load_dotenv
from openai import AsyncOpenAI

from breba_app.generator_agent.instruction_reader import get_instructions

load_dotenv()

client = AsyncOpenAI()

SYSTEM_PROMPT = get_instructions("generator_diffing_prompt")


async def diff_stream(html: str, prompt: str):
    print("Generating diff")
    stream = await client.responses.create(
        model="gpt-4.1",
        temperature=0,
        instructions=SYSTEM_PROMPT,
        stream=True,
        input=[
            {
                "role": "user",
                "content": f"#Given the following HTML:\n{html}\n\n"
                           f"##User Request:\n{prompt}"
            },
        ],
    )

    async for event in stream:
        if event.type == "response.output_text.delta":
            yield event.delta


async def diff_text(html: str, prompt: str):
    diff = ""
    async for chunk in diff_stream(html, prompt):
        diff += chunk
    return diff
