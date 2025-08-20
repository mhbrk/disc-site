import difflib
import logging

from agent_model import TextPart, Message
from breba_app.diff import PatchApplyError
from builder_agent.agent import agent as builder_agent
from generator_agent.accumulator import TagAccumulator
from generator_agent.agent import agent as generator_agent

logger = logging.getLogger(__name__)


def get_generator_response(session_id: str):
    return generator_agent.get_last_html(session_id)


def set_generator_response(session_id: str, html_output: str):
    generator_agent.set_last_html(session_id, html_output)


def get_html_diff(old_html: str, new_html: str):
    diff = difflib.unified_diff(
        old_html.splitlines(),
        new_html.splitlines(),
        fromfile='a',
        tofile='b',
        lineterm=''
    )
    return "\n".join(diff)


async def process_chunk(accumulator: TagAccumulator, chunk: dict, generator_callback):
    logger.info(f"Processing chunk from agent: {chunk}")
    content = chunk.get("content")
    if not content:
        return

    is_task_completed = chunk.get("is_task_complete")

    # TODO: handle the case when input is required
    if is_task_completed:
        await generator_callback("__completed__")
    else:
        tag_html = accumulator.append_and_return_html(content)
        if not tag_html:
            # Accumulate more text before publishing chunk.
            return
        logger.info(f"HTML tag exists: {tag_html}")
        await generator_callback(tag_html)


async def start_streaming_task(user_name: str, session_id: str, query: str, generator_callback):
    accumulator = TagAccumulator()
    async for chunk in generator_agent.stream(query, user_name, session_id):
        await process_chunk(accumulator, chunk, generator_callback)


async def start_editing_task(user_name: str, session_id: str, query: str, generator_callback):
    try:
        update = await generator_agent.diffing_update(query, session_id)
        # TODO: this is funky. Using generator_callback like this needs to be codified. Maybe use a class instead of a function
        await generator_callback(update)
        await generator_callback("__completed__")
    except Exception as e:
        logger.error(f"Error applying patch: {e}")
        accumulator = TagAccumulator()
        async for chunk in generator_agent.editing_stream(query, user_name, session_id):
            await process_chunk(accumulator, chunk, generator_callback)


async def to_generator(user_name: str, session_id: str, message: str, builder_completed_callback, generator_callback,
                       message_to_user_callback):
    old_html = generator_agent.get_last_html(session_id)
    await message_to_user_callback("Generator is processing your request...")
    await start_editing_task(user_name, session_id, message, generator_callback)
    new_html = generator_agent.get_last_html(session_id)
    # TODO: use diff module
    diff = get_html_diff(old_html, new_html)

    agent_message = Message(role="user", parts=[TextPart(text=f"{message} \n"
                                                              f"\n In response to the user message, the generator modified the output according to this diff {diff}.\n"
                                                              f"When a user requests a change to the website, update the website specification to reflect the new requirement, unless the requested change is already explicitly included in the current specification. Only refrain from updating the specification if the issue was due to an implementation error (i.e., the generator did not follow the existing specification)."
                                                              f"IMPORTANT: If the diff shows that an the issue stemmed from a bug in the implementation, do not modify the website specification.")])

    # TODO: should probably ask user to confirm
    await message_to_user_callback(
        "Rebuilding the specification... Please wait for completion before doing anything else")
    agent_response = await builder_agent.invoke(user_name, session_id, agent_message)
    await message_to_user_callback("Rebuild specification task is now complete.")

    content = agent_response.get("content")
    is_task_completed = agent_response.get("is_task_complete")

    if is_task_completed:
        await builder_completed_callback(content)
    else:
        logger.info(f"Waiting for user input: {content}")
        await message_to_user_callback(content)


async def to_builder(user_name: str, session_id: str, message: str, builder_completed_callback,
                     message_to_user_callback,
                     generator_callback):
    agent_message = Message(role="user", parts=[TextPart(text=message)])
    await message_to_user_callback("Builder is working on the specification...")
    agent_response = await builder_agent.invoke(user_name, session_id, agent_message)
    content = agent_response.get("content")
    is_task_completed = agent_response.get("is_task_complete")

    if is_task_completed:
        await builder_completed_callback(content)
        await message_to_user_callback(
            "Generating preview for the new spec... Use the 📄 from the sidebar to check the new spec")
        await start_streaming_task(user_name, session_id, content, generator_callback)
    else:
        logger.info(f"Waiting for user input: {content}")
        await message_to_user_callback(content)


async def update_builder_spec(session_id: str, message: str):
    agent_response = await builder_agent.set_agent_prompt(session_id, message)
    return agent_response
