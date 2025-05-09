import asyncio
import logging
import os

import httpx

from common.constants import BUILDER_AGENT_TOPIC
from common.utils import subscribe_to_agent

logger = logging.getLogger(__name__)
# These host and port values are not the same as receive url because
# they are used to ping the server to see if it started,
# while receive url is used to subscribe to pubsub and is the url for accessing agent form the outside world
HOST = os.getenv("AGENT_HOST", "localhost")
PORT = int(os.getenv("AGENT_PORT", 8080))

RECEIVE_URL: str = os.getenv("RECEIVE_URL", f"http://{HOST}:{PORT}")

async def wait_for_server_ready(url: str, timeout: float = 30.0):
    logger.info(f"Waiting for server to start at {url}")
    async with httpx.AsyncClient() as client:
        for _ in range(int(timeout * 10)):
            try:
                response = await client.get(url)
                if response.status_code < 500:
                    logger.info("✅ Server is ready.")
                    return
            except httpx.RequestError:
                pass
            await asyncio.sleep(0.1)
    raise TimeoutError(f"Server did not start within {timeout} seconds")

async def subscribe_to_agents():
    # TODO: check for pubsub being up instead of sleeping
    await wait_for_server_ready(f"http://{HOST}:{PORT}/health")
    await subscribe_to_agent(BUILDER_AGENT_TOPIC, RECEIVE_URL)



if __name__ == "__main__":
    asyncio.run(subscribe_to_agents())