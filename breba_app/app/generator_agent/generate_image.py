import asyncio
import json
import logging
import uuid

import httpx
from dotenv import load_dotenv
from langchain_core.tools import tool
from openai import AsyncOpenAI

from common.storage import save_image_to_private

logger = logging.getLogger(__name__)

load_dotenv()

client = AsyncOpenAI()


async def _generate_and_save_image(session_id: str, task_id: str, prompt: str, image_name: str):
    try:
        result = await client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size="1024x1024",
            response_format="url",
            quality="standard"
        )

        json_response = json.loads(result.model_dump_json())
        image_url = json_response["data"][0]["url"]

        response = await httpx.AsyncClient().get(image_url)
        image = response.content

        save_image_to_private(session_id, image_name, image)


    except Exception as e:
        logger.error(f"[{task_id}] Error generating or sending image: {e}")


@tool
async def generate_image(session_id: str, task_id: str, prompt: str) -> str:
    """
    This tool starts to generate images. It will return image path, and then start to generate the image.
    For better outcomes provide some context regarding where and how the image will be used.

        Args:
            session_id: The session id
            task_id: The task id
            prompt: The prompt to generate the image. For better outcomes provide some context regarding where and how the image will be used.

        Returns:
            The image file name.
        """
    logger.info(f"[{task_id}] Generating image for prompt: {prompt}")
    image_name = f"{uuid.uuid4().hex}.png"

    # Kick off background image generation + response sending
    asyncio.create_task(_generate_and_save_image(session_id, task_id, prompt, image_name))

    # TODO: store in the cloud. That would remove dependency on knowing the "images" directory
    return f"Generated image: ./images/{image_name}"


if __name__ == "__main__":

    async def main():
        asyncio.create_task(generate_image.ainvoke({
            "session_id": "user-1-session-1",
            "task_id": "task-1",
            "prompt": "a close-up of a bear walking through the forest"
        }))
        await asyncio.sleep(1)  # wait for the task to start
        current = asyncio.current_task()
        tasks = [t for t in asyncio.all_tasks() if t is not current]

        if tasks:
            print(f"Waiting for {len(tasks)} tasks...")
            await asyncio.gather(*tasks)


    load_dotenv()
    asyncio.run(main())
