import logging

from builder_agent.agent import agent as builder_agent
from common.model import TextPart, Message
from generator_agent.accumulator import TagAccumulator
from generator_agent.agent import agent as generator_agent

logger = logging.getLogger(__name__)


def get_generator_response(session_id: str):
    return generator_agent.get_last_html(session_id)


def set_generator_response(session_id: str, html_output: str):
    generator_agent.set_last_html(session_id, html_output)


async def start_streaming_task(user_name: str, session_id: str, query: str, generator_callback):
    accumulator = TagAccumulator()
    async for chunk in generator_agent.stream(query, user_name, session_id):
        logger.info(f"Processing chunk from agent: {chunk}")
        content = chunk.get("content")
        if not content:
            continue

        is_task_completed = chunk.get("is_task_complete")

        # TODO: handle the case when input is required
        if is_task_completed:
            await generator_callback("__completed__")
        else:
            tag_html = accumulator.append_and_return_html(content)
            if not tag_html:
                # Accumulate more text before publishing chunk.
                continue
            logger.info(f"HTML tag exists: {tag_html}")
            await generator_callback(tag_html)


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
