import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from openai import AsyncOpenAI

client = AsyncOpenAI()

logger = logging.getLogger(__name__)


async def get_product_name(description: str) -> str:
    if not description:
        raise ValueError("description cannot be empty")

    prompt = (
        f"Create a product name given the description. *Important:* your response must be one to three words long."
        f" <BEGIN DESCRIPTION>\n{description}\n<END DESCRIPTION>\n\n"
        f"**Your response must be a one to three words long description of the product above.**")

    try:
        response = await client.responses.create(model="gpt-5-nano", input=prompt,
                                                 reasoning={"effort": "minimal"},
                                                 text={"verbosity": "low"})
        return response.output_text
    except Exception as e:
        logger.error(f"Product name generation failed: {e}")
        # This is not a critical function. Just return the first word of the description
        return description.split()[0]


def get_instructions(agent_dir: Path, name, **kwargs):
    env = Environment(loader=FileSystemLoader(agent_dir / "instructions"))
    template = env.get_template(f"{name}.jinja2")
    return template.render(**kwargs)
