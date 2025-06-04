import logging

from builder_agent.agent import BuilderAgent
from common.model import TextPart, Message
from generator_agent.accumulator import TagAccumulator
from generator_agent.agent import HTMLAgent

logger = logging.getLogger(__name__)

builder_agent = BuilderAgent()
generator_agent = HTMLAgent()


def get_generator_response(session_id: str):
    return generator_agent.get_last_html(session_id)


async def start_streaming_task(session_id: str, query: str, generator_callback):
    accumulator = TagAccumulator()
    async for chunk in generator_agent.stream(query, session_id, session_id):
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


async def to_builder(session_id: str, message: str, builder_completed_callback, ask_user_callback, generator_callback):
    agent_message = Message(role="user", parts=[TextPart(text=message)])

    agent_response = await builder_agent.invoke(session_id, agent_message)
    content = agent_response.get("content")
    is_task_completed = agent_response.get("is_task_complete")

    if is_task_completed:
        await builder_completed_callback(content)
        await start_streaming_task(session_id, content, generator_callback)
    else:
        logger.info(f"Waiting for user input: {content}")
        await ask_user_callback(content)
