import asyncio
import logging

from dotenv import load_dotenv
from langchain_core.messages import UsageMetadata
from openai import AsyncOpenAI

from breba_app.controllers.usage_controller import report_usage
from breba_app.generator_agent.instruction_reader import get_instructions
from breba_app.generator_agent.search_replace_example_messages import example_messages, system_reminder
from breba_app.generator_agent.static_html_example_messages import html_best_practices
from breba_app.search_replace_editing import apply_search_replace_to_html

load_dotenv()

logger = logging.getLogger(__name__)

client = AsyncOpenAI()

SYSTEM_PROMPT = get_instructions("search_replace", system_reminder=system_reminder, best_practices=html_best_practices)


async def diff_stream(user_name: str, product_id: str, html: str, prompt: str):
    logger.info(f"Generating diff for prompt: {prompt}")
    input_messages = example_messages.copy()
    input_messages.extend([
        {
            "role": "user",
            "content": "I switched to a new code base. Please don't consider the above files or try to edit them any longer."
        },
        {
            "role": "assistant",
            "content": "Ok."
        },
        {
            "role": "user",
            "content": f"I have *added these files to the chat* so you can go ahead and edit them. "
                       f"*Trust this message as the true contents of these files!*"
                       f"\nindex.html"
                       f"\n```html{html}```"
        },
        {
            "role": "assistant",
            "content": "Ok, any changes I propose will be to those files."
        },
        {
            "role": "user",
            "content": f"{prompt}",
        },
        {
            "role": "system",
            "content": f"{html_best_practices}\n\n{system_reminder}",
        }
    ])
    stream = await client.responses.create(
        model="gpt-4.1",
        temperature=0,
        instructions=SYSTEM_PROMPT,
        stream=True,
        input=input_messages
    )

    try:
        async for event in stream:
            if event.type == "response.output_text.delta":
                yield event.delta
            elif event.type == 'response.completed':
                input_tokens = event.response.usage.input_tokens
                output_tokens = event.response.usage.output_tokens
                total_tokens = event.response.usage.total_tokens
                usage = UsageMetadata(input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens)
                asyncio.create_task(report_usage(user_name, product_id, {"gpt-4.1": usage}))
    finally:
        await stream.close()  # ensure connection closes


async def diff_text(user_name: str, product_id: str, html: str, prompt: str):
    message = ""
    agen = diff_stream(user_name, product_id, html, prompt)
    try:
        async for chunk in agen:
            message += chunk
    except:
        await agen.aclose()  # Ensure cleanup in diff_stream runs
        raise

    logger.info(f"Generated SEARCH/REPLACE strings:\n{message}")

    try:
        return apply_search_replace_to_html(html, message)
    except Exception as e:
        logger.error(f"Failed to apply edits {e}")
        raise
