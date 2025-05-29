import os

from builder_agent.agent import BuilderAgent

from common.constants import ASK_CHAT_AGENT_TOPIC, BUILDER_AGENT_TOPIC
from common.model import TextPart, Message, Artifact, TaskStatus, TaskState, Task, SendTaskResponse, TaskSendParams, SendTaskStreamingRequest
from common.utils import publish_to_topic

import httpx

builder_agent = BuilderAgent()


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


async def process_user_message(session_id, message: str):
    url = os.getenv("RECEIVE_URL", "http://0.0.0.0:8080")
    agent_message = Message(role="user", parts=[TextPart(text=message)])

    agent_response = await builder_agent.invoke(session_id, agent_message)
    content = agent_response.get("content")
    is_task_completed = agent_response.get("is_task_complete")

    if is_task_completed:
        await publish_task_request(session_id, session_id, content)
        await publish_task_response(session_id, session_id, content, TaskState.COMPLETED)
    else:
        await publish_task_response(session_id, session_id, content,
                              TaskState.INPUT_REQUIRED)



