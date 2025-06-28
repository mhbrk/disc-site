from openai import AsyncOpenAI

client = AsyncOpenAI()


async def get_product_name(description: str) -> str:
    prompt = (
        f"Create a product name given the description. Should be no more than 3 words. Description: {description}")

    response = await client.responses.create(model="gpt-4.1-nano", input=prompt)

    return response.output_text
