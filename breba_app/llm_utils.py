from openai import AsyncOpenAI

client = AsyncOpenAI()


async def get_product_name(description: str) -> str:
    prompt = (
        f"Create a product name given the description. *Important:* your response must be one to three words long."
        f" <BEGIN DESCRIPTION>\n{description}\n<END DESCRIPTION>\n\n"
        f"**Your response must be a one to three words long description of the product above.**")

    response = await client.responses.create(model="gpt-4.1-nano", input=prompt)

    return response.output_text
