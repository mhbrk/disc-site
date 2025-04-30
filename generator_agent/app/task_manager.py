import asyncio

from dotenv import load_dotenv

from accumulator import TagAccumulator
from common.constants import GENERATOR_AGENT_TOPIC
from common.model import TextPart, Message, Artifact, TaskStatus, TaskState, Task, SendTaskResponse, \
    SendTaskStreamingRequest, SendTaskStreamingResponse, TaskStatusUpdateEvent, TaskArtifactUpdateEvent
from common.utils import publish_to_topic

load_dotenv()

from agent import agent


async def execute_task(task_request: SendTaskStreamingRequest):
    params = task_request.params
    query = params.message.parts[0].text
    session_id = params.sessionId
    task_id = params.id

    # Start the streaming agent in the background
    asyncio.create_task(start_streaming_task(task_id, session_id, query))

    status = TaskStatus(
        state=TaskState.SUBMITTED,
        message=Message(
            role="agent",
            parts=[TextPart(text="Streaming has started. You will receive updates shortly.")]
        )
    )
    update: TaskStatusUpdateEvent = TaskStatusUpdateEvent(id=task_id, status=status, metadata={"sessionId": session_id})
    response = SendTaskStreamingResponse(result=update).model_dump(exclude_none=True)
    asyncio.create_task(publish_to_topic(GENERATOR_AGENT_TOPIC, response, task_id))

    return response


async def publish_task_response(task_id: str, session_id: str, content: str):
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


async def publish_artifact_update(task_id: str, session_id: str, content: str):
    artifact = Artifact(parts=[TextPart(text=content)])

    update = TaskArtifactUpdateEvent(id=task_id, artifact=artifact, metadata={"sessionId": session_id})

    response = SendTaskStreamingResponse(result=update)

    await publish_to_topic(GENERATOR_AGENT_TOPIC, response.model_dump(exclude_none=True), task_id)


async def start_streaming_task(task_id: str, session_id: str, query: str):
    accumulator = TagAccumulator()
    async for chunk in agent.stream(query, session_id, task_id):
        content = chunk.get("content")
        if not content:
            continue

        is_task_completed = chunk.get("is_task_complete")

        # TODO: handle the case when input is required
        if is_task_completed:
            await publish_task_response(task_id, session_id, content)
        else:
            tag_html = accumulator.append_and_return_html(content)
            if not tag_html:
                # Accumulate more text before publishing chunk.
                continue
            await publish_artifact_update(task_id, session_id, tag_html)


if __name__ == "__main__":
    query = """
        
    HTML Site for 3-Day Weather Forecast

    Visual layout:
    - The site should have a clear title or header indicating "3-Day Weather Forecast for Redmond, WA".
    - The forecast should be displayed in a simple, clean layout that works well on both desktop and mobile devices.

    Forecast display:
    - For each of the next 3 days, show:
      - The date of the forecast in bold, using the format "Month Day" (e.g., "October 12").
      - An image representing the weather for that day (e.g., sun, clouds, rain).
      - The high and low temperatures in Fahrenheit.
      - The chance of precipitation (as a percentage).

    Data source:
    - Include a link to the exact source page for the Redmond, WA weather forecast at the bottom of the page.
    - If an exact source link for Redmond, WA is not available, do not display the forecast and instead show the following error message: "Weather forecast is currently unavailable because a direct source link for Redmond, WA could not be found."

    Behavior:
    - The forecast should load automatically when the page is opened (no refresh or update button needed).

    Styling:
    - Use a simple, default design that is easy to read and visually clear.
    - Display the date for each day in bold.
    """


    async def main():
        asyncio.create_task(start_streaming_task("abc123", "user-1-session-1", query))
        await asyncio.sleep(1)  # wait for the task to start
        current = asyncio.current_task()
        tasks = [t for t in asyncio.all_tasks() if t is not current]

        if tasks:
            print(f"Waiting for {len(tasks)} tasks...")
            await asyncio.gather(*tasks)


    asyncio.run(main())
