import logging
import os

from builder_agent.agent import BuilderAgent
from common.constants import ASK_CHAT_AGENT_TOPIC, BUILDER_AGENT_TOPIC, GENERATOR_AGENT_TOPIC
from common.model import TextPart, Message, Artifact, TaskStatus, TaskState, Task, SendTaskResponse, TaskSendParams, \
    SendTaskStreamingRequest, TaskArtifactUpdateEvent, SendTaskStreamingResponse
from common.utils import publish_to_topic
from generator_agent.accumulator import TagAccumulator
from generator_agent.agent import HTMLAgent

logger = logging.getLogger(__name__)

builder_agent = BuilderAgent()
generator_agent = HTMLAgent()


async def publish_task_request(task_id: str, session_id: str, message: str):
    """
    This function will publish task request to the builder agent topic.
    Basically provoking other agents to pick up the task.
    Use this when builder has finished building the spec
    """
    message = Message(role="user", parts=[TextPart(text=message)])

    task_params = TaskSendParams(
        id=task_id,
        sessionId=session_id,
        message=message
    )
    request = SendTaskStreamingRequest(params=task_params)

    await publish_to_topic(BUILDER_AGENT_TOPIC, request.model_dump(exclude_none=True), task_id)


async def publish_task_response(task_id: str, session_id: str, content: str, task_state: TaskState):
    """
    This function will publish task response to the ask chat agent topic. Use this to get additional user input or complete task
    """
    # When we are invoking the agent, if task is not complete, we assume it is waiting for user input
    # Even if there is an error, the only resolution that is possible, is another message from client
    if task_state == TaskState.INPUT_REQUIRED:
        # If input required, we want to have status text, but not artifact text
        status_text = content
        artifact_text = ""
    else:
        status_text = ""
        artifact_text = content

    message = Message(role="agent", parts=[TextPart(text=status_text)])
    task_status = TaskStatus(message=message, state=task_state)

    artifact = Artifact(parts=[TextPart(text=artifact_text)])

    task = Task(
        id=task_id,
        sessionId=session_id,
        status=task_status,
        artifacts=[artifact],  # or keep None if artifacts are sent at the end
        metadata={}
    )

    response = SendTaskResponse(result=task)

    await publish_to_topic(ASK_CHAT_AGENT_TOPIC, response.model_dump(exclude_none=True), task_id)


async def publish_artifact_update(task_id: str, session_id: str, content: str):
    artifact = Artifact(parts=[TextPart(text=content)])

    update = TaskArtifactUpdateEvent(id=task_id, artifact=artifact, metadata={"sessionId": session_id})

    response = SendTaskStreamingResponse(result=update)

    await publish_to_topic(GENERATOR_AGENT_TOPIC, response.model_dump(exclude_none=True), task_id)


async def publish_generator_completed(task_id: str, session_id: str, content: str):
    task_status = TaskStatus(state=TaskState.COMPLETED)
    artifact = Artifact(parts=[TextPart(text=content)])

    task = Task(
        id=task_id,
        sessionId=session_id,
        status=task_status,
        artifacts=[artifact],
        metadata={}
    )

    response = SendTaskResponse(result=task)
    await publish_to_topic(GENERATOR_AGENT_TOPIC, response.model_dump(exclude_none=True), task_id)


async def start_streaming_task(task_id: str, session_id: str, query: str):
    accumulator = TagAccumulator()
    async for chunk in generator_agent.stream(query, session_id, task_id):
        logger.info(f"Processing chunk from agent: {chunk}")
        content = chunk.get("content")
        if not content:
            continue

        is_task_completed = chunk.get("is_task_complete")

        # TODO: handle the case when input is required
        if is_task_completed:
            await publish_generator_completed(task_id, session_id, content)
        else:
            tag_html = accumulator.append_and_return_html(content)
            if not tag_html:
                # Accumulate more text before publishing chunk.
                continue
            logger.info(f"HTML tag exists: {tag_html}")
            await publish_artifact_update(task_id, session_id, tag_html)


async def process_user_message(session_id, message: str):
    url = os.getenv("RECEIVE_URL", "http://0.0.0.0:8080")
    agent_message = Message(role="user", parts=[TextPart(text=message)])

    agent_response = await builder_agent.invoke(session_id, agent_message)
    content = agent_response.get("content")
    is_task_completed = agent_response.get("is_task_complete")

    if is_task_completed:
        await publish_task_request(session_id, session_id, content)
        await publish_task_response(session_id, session_id, content, TaskState.COMPLETED)
        await start_streaming_task(session_id, session_id, content)
    else:
        await publish_task_response(session_id, session_id, content,
                                    TaskState.INPUT_REQUIRED)
