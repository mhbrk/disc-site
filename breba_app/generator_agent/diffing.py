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

    try:
        async for event in stream:
            if event.type == "response.output_text.delta":
                yield event.delta
    finally:
        await stream.close()  # ensure connection closes


async def diff_text(html: str, prompt: str, max_lines: int = 100):
    diff = ""
    agen = diff_stream(html, prompt)
    try:
        async for chunk in agen:
            diff += chunk
            if len(diff.splitlines()) > max_lines:
                raise Exception("Diff too long")
    except:
        await agen.aclose()  # Ensure cleanup in diff_stream runs
        raise
    return diff
