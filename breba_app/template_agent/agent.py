from typing import AsyncIterable

from breba_app.template_agent.baml_client.async_client import b
from breba_app.template_agent.baml_client.stream_types import Question as StreamQuestion, LLMMessage, \
    WebsiteSpecification as StreamWebSpecification
from breba_app.template_agent.baml_client.types import WebsiteSpecification, Question
from breba_app.template_agent.memory_store import get_messages, save_messages


async def to_user_stream(streamer: AsyncIterable[StreamQuestion | StreamWebSpecification]):
    spec_started = False
    async for msg in streamer:
        if type(msg) is StreamQuestion:
            yield msg.question
        if type(msg) is StreamWebSpecification:
            if not spec_started:
                spec_started = True
                yield "Builder is working on the specification..."


class TemplateAgent:
    def __init__(self, user_name: str, product_id: str, messages: list[LLMMessage] | None = None):
        self.user_name = user_name
        self.product_id = product_id
        # TODO: restore state from inMemory saver
        self.messages: list[LLMMessage] = messages or get_messages(user_name, product_id)

    async def build_specification(self, message: str, ask_user_streaming_callback) -> WebsiteSpecification:
        self.messages.append(LLMMessage(role="user", content=message))
        stream = b.stream.GenerateSpecificationFromTemplate(self.messages)

        await ask_user_streaming_callback(to_user_stream(stream))

        agent_response = await stream.get_final_response()

        if isinstance(agent_response, Question):
            self.messages.append(LLMMessage(role="assistant", content=agent_response.question))
        elif isinstance(agent_response, WebsiteSpecification):
            self.messages.append(LLMMessage(role="assistant", content=agent_response.spec))

        save_messages(self.user_name, self.product_id, self.messages)

        return agent_response
