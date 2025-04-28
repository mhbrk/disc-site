import os

from dotenv import load_dotenv

from accumulator import TagAccumulator
from common.constants import GENERATOR_AGENT_TOPIC
from common.model import TextPart, Message, Artifact, TaskStatus, TaskState, Task, SendTaskResponse
from common.utils import publish_to_topic

load_dotenv()

from agent import agent

PUBSUB_URL = os.environ.get("PUBSUB_URL", "http://localhost:8000")


async def start_streaming_task(task_id: str, session_id: str, query: str):
    accumulator = TagAccumulator()
    async for chunk in agent.stream(query, session_id, task_id):
        content = chunk.get("content")
        if not content:
            continue

        is_task_completed = chunk.get("is_task_complete")

        # TODO: handle the case when input is required
        if is_task_completed:
            task_status = TaskStatus(state=TaskState.COMPLETED)
        else:
            content = accumulator.append_and_return_html(content)
            if not content:
                # Accumulate more text before publishing chunk.
                continue
            message = Message(role="agent", parts=[TextPart(text="Streaming...")])
            task_status = TaskStatus(message=message, state=TaskState.WORKING)

        artifact = Artifact(parts=[TextPart(text=content)])

        task = Task(
            id=task_id,
            sessionId=session_id,
            status=task_status,
            artifacts=[artifact],  # or keep None if artifacts are sent at the end
            metadata={}
        )

        response = SendTaskResponse(result=task)

        await publish_to_topic(GENERATOR_AGENT_TOPIC, response.model_dump(exclude_none=True), task_id)


if __name__ == "__main__":
    import asyncio

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
