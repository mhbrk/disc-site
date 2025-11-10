from typing import AsyncIterable

from breba_app.template_agent.baml_client.async_client import b
from breba_app.template_agent.baml_client.stream_types import Question
from breba_app.template_agent.baml_client.types import WebsiteSpecification


async def to_user_stream(streamer: AsyncIterable[Question | WebsiteSpecification]):
    async for msg in streamer:
        if type(msg) is Question:
            yield msg.question


class TemplateAgent:
    def __init__(self, user_name: str, product_id: str):
        self.user_name = user_name
        self.product_id = product_id
        # TODO: restore state from inMemory saver
        messages = []

    async def build_specification(self, template_text: str, ask_user_streaming_callback) -> WebsiteSpecification:
        # TODO: handle message history

        stream = b.stream.GenerateSpecificationFromTemplate(template_text)

        await ask_user_streaming_callback(to_user_stream(stream))

        return await stream.get_final_response()
