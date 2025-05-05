import asyncio

from mcp import ClientSession
from mcp.client.sse import sse_client


async def main():
    url = "http://localhost:8004/sse"  # << THIS is the correct endpoint

    async with sse_client(url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Session initialized successfully!")

            # Example: Ping
            pong = await session.send_ping()
            print(f"Ping response: {pong}")

if __name__ == "__main__":
    asyncio.run(main())
