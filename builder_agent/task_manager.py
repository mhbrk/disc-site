import logging
import os
import uuid

from dotenv import load_dotenv

from common.constants import ASK_CHAT_AGENT_TOPIC, BUILDER_AGENT_TOPIC
from common.model import TextPart, Message, Artifact, TaskStatus, TaskState, Task, SendTaskResponse, SendTaskRequest, \
    TaskSendParams
from common.utils import publish_to_topic

# Needs to happen before agent
load_dotenv()

from agent import agent

logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)

PUBSUB_URL = os.environ.get("PUBSUB_URL", "http://localhost:8000")


class AgentTaskManager:
    async def publish_task_request(self, task_id: str, session_id: str, message: str):
        message = Message(role="user", parts=[TextPart(text=message)])

        task_params = TaskSendParams(
            id=task_id,
            sessionId=session_id,
            message=message
        )
        request = SendTaskRequest(params=task_params)

        await publish_to_topic(BUILDER_AGENT_TOPIC, request.model_dump(exclude_none=True), task_id)

    async def publish_task_response(self, task_id: str, session_id: str, content: str, task_state: TaskState):
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

    async def on_send_task(self, request: SendTaskRequest):
        logger.info(f"[{request.params.id}] Received task: {request.params.message}")
        agent_response = await agent.invoke(request.params.sessionId, request.params.message)
        content = agent_response.get("content")
        is_task_completed = agent_response.get("is_task_complete")

        if is_task_completed:
            await self.publish_task_request(request.params.id, request.params.sessionId, content)
            # Publish to ask chat agent topic, so that it knows that task is complete. Ideally, this topic should
            # come from task request
            await self.publish_task_response(request.params.id, request.params.sessionId, content,
                                             TaskState.COMPLETED)
        else:
            # When we are invoking the agent, if task is not complete, we assume it is waiting for user input
            # Even if there is an error, the only resolution that is possible, is another message from client
            await self.publish_task_response(request.params.id, request.params.sessionId, content,
                                             TaskState.INPUT_REQUIRED)


if __name__ == "__main__":
    import asyncio

    task_manager = AgentTaskManager()
    message = Message(
        role="user",
        parts=[
            TextPart(
                text="Generate a site for my birthday. I'm turning 18. My birthday is on June 11 and the theme is 1990s.")
        ]
    )

    # Wrap in TaskSendParams
    task_id = f"task-{uuid.uuid4().hex}"
    task_params = TaskSendParams(
        id=task_id,
        sessionId="user-1-session-1",
        message=message
    )

    test_request = SendTaskRequest(
        params=task_params,
        id=str(uuid.uuid4())  # or pass your own
    )
    asyncio.run(task_manager.on_send_task(test_request))
