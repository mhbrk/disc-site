import asyncio
import json
import os
import uuid

import httpx
from dotenv import load_dotenv
from langchain_core.tools import tool
from openai import AsyncAzureOpenAI

from common.model import Artifact, Task, TaskState, TaskStatus, SendTaskResponse, FilePart, FileContent

load_dotenv()

PUBSUB_URL = os.environ.get("PUBSUB_URL", "http://localhost:8000")
PUBSUB_TOPIC = "generator_agent_topic"

client = AsyncAzureOpenAI(
    api_version="2024-02-01",
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT']
)


async def send_task_response(task_id: str, session_id: str, image_name: str, image_location: str):
    file_content: FileContent = FileContent(name=image_name, uri=image_location, mimeType="image/png")
    artifact = Artifact(parts=[FilePart(file=file_content)])

    task_status = TaskStatus(state=TaskState.WORKING)
    task = Task(
        id=task_id,
        sessionId=session_id,
        status=task_status,
        artifacts=[artifact],  # or keep None if artifacts are sent at the end
        metadata={}
    )

    response = SendTaskResponse(id=task_id, result=task)

    payload = {
        "topic": PUBSUB_TOPIC,
        "payload": response.model_dump(exclude_none=True)
    }

    async with httpx.AsyncClient() as client:
        try:
            print(f"[{task_id}] Publishing to pubsub: {payload}")
            await client.post(f"{PUBSUB_URL}/publish", json=payload)
        except Exception as e:
            print(f"[{task_id}] Failed to publish to pubsub: {e}")


async def _generate_and_send_image(session_id: str, task_id: str, prompt: str, image_name: str):
    try:
        result = await client.images.generate(
            model="dalle3",
            prompt=prompt,
            n=1,
            size="1024x1024",
            response_format="url",
            quality="standard"
        )

        json_response = json.loads(result.model_dump_json())
        image_url = json_response["data"][0]["url"]

        # Send task response
        await send_task_response(task_id, session_id, image_name, image_url)

    except Exception as e:
        print(f"[{task_id}] Error generating or sending image: {e}")


@tool
async def generate_image(session_id: str, task_id: str, prompt: str) -> str:
    """This tool starts to generate images. It will return image path, and then start to generate the image.

        Args:
            session_id: The session id
            task_id: The task id
            prompt: The prompt to generate the image.

        Returns:
            The image file name.
        """
    image_name = f"{task_id}{uuid.uuid4().hex}.png"

    # Kick off background image generation + response sending
    asyncio.create_task(_generate_and_send_image(session_id, task_id, prompt, image_name))


    # TODO: store in the cloud. That would remove dependency on knowing the "images" directory
    return f"Generated image: /images/{image_name}"


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(generate_image("user-1-session-1", "task-1", "a close-up of a bear walking through the forest"))
