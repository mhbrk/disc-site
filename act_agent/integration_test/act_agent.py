import httpx
import asyncio


async def call_act_endpoint():
    url = "http://localhost:7999/act"  # Change if your server is running elsewhere
    payload = 'Save the following data: {"name": "John", "age": 30}'

    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            url,
            content=payload,  # Send raw string payload
            headers={"Content-Type": "text/plain"}  # Important: set Content-Type
        )
        print(response.status_code)
        print(response.json())


# To run it
if __name__ == "__main__":
    asyncio.run(call_act_endpoint())
