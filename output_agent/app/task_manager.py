import httpx

from dotenv import load_dotenv

load_dotenv()

from output_agent.app.agent import agent

PUBSUB_URL = "http://localhost:8000/publish"
PUBSUB_TOPIC = "a2a-task-stream"


async def start_streaming_task(task_id: str, session_id: str, query: str):
    async for chunk in agent.stream(query, session_id):
        content = chunk.get("content")
        if not content:
            continue
        payload = {
            "topic": PUBSUB_TOPIC,
            "payload": {
                "id": task_id,
                "status": {
                    "state": "working",
                    "message": {
                        "role": "agent",
                        "parts": [{
                            "type": "text",
                            "text": content
                        }]
                    }
                },
                "final": chunk.get("is_task_complete", False),
                "metadata": {}
            }
        }

        async with httpx.AsyncClient() as client:
            try:
                print(f"[{task_id}] Publishing to pubsub: {payload}")
                # await client.post(PUBSUB_URL, json=payload)
            except Exception as e:
                print(f"[{task_id}] Failed to publish to pubsub: {e}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(start_streaming_task("abc123", "def456", "generate a hello world site"))
