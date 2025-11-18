from typing import AsyncIterable

from langchain_core.messages import trim_messages
from langchain_core.messages.utils import count_tokens_approximately, convert_to_openai_messages

from breba_app.template_agent.baml_client.async_client import b
from breba_app.template_agent.baml_client.stream_types import Question as StreamQuestion, LLMMessage, \
    WebsiteSpecification as StreamWebSpecification
from breba_app.template_agent.baml_client.types import WebsiteSpecification, Question
from breba_app.template_agent.memory_store import load_state, save_state

TOKEN_LIMIT = 100_000


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
        self.state = load_state(user_name, product_id)
        if messages:
            self.state.messages = messages

    async def build_specification(self, message: str, ask_user_streaming_callback) -> WebsiteSpecification | Question:
        self.state.messages.append(LLMMessage(role="user", content=message))
        dict_messages = [message.model_dump() for message in self.state.messages]
        # "human" is the langchain type for "user" role messages
        trimmed_messages_lc = trim_messages(dict_messages, strategy="last",
                                            token_counter=count_tokens_approximately, max_tokens=TOKEN_LIMIT,
                                            start_on=["human"], include_system=True)

        trimmed_messages = convert_to_openai_messages(trimmed_messages_lc)

        if trimmed_messages:
            # We are just going to pass a dict that has proper duck type
            stream = b.stream.GenerateSpecificationFromTemplate(trimmed_messages)
            await ask_user_streaming_callback(to_user_stream(stream))
            agent_response = await stream.get_final_response()
            if isinstance(agent_response, Question):
                self.state.messages.append(LLMMessage(role="assistant", content=agent_response.question))
            elif isinstance(agent_response, WebsiteSpecification):
                self.state.messages.append(LLMMessage(role="assistant", content=agent_response.spec))
            save_state(self.user_name, self.product_id, self.state)
        else:
            # This will only happen when the last user message is very long.
            # We do not want to add it to the state because it will hide all older messages. So we will not save state
            self.state.messages.pop()
            message = f"You have exceeded the token limit({TOKEN_LIMIT} tokens). Please provide a shorter description."
            await ask_user_streaming_callback(message)
            agent_response = Question(question=message)

        return agent_response
