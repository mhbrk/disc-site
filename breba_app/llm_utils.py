from openai import AsyncOpenAI

client = AsyncOpenAI()


async def get_product_name(description: str) -> str:
    prompt = (
        f"Create a product name given the description. *Important:* your response must be one to three words long."
        f" Description: {description}")

    response = await client.responses.create(model="gpt-4.1-nano", input=prompt)

    return response.output_text
