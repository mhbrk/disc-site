import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import AsyncIterable, AsyncIterator

from baml_py import BamlStream

from breba_app.coder_agent.agent import stream_user_response_or_coder, run_coder_agent
from breba_app.coder_agent.baml_client.stream_types import Coder as CoderStream, ResponseToUser as ResponseToUserStream
from breba_app.coder_agent.baml_client.types import LLMMessage, Coder, ResponseToUser
from breba_app.config import INDEX_FILE_NAME
from breba_app.filesystem import InMemoryFileStore
from breba_app.status_service import agent_task, update_status
from breba_app.template_agent.agent import TemplateAgent
from breba_app.template_agent.baml_client.types import WebsiteSpecification

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorState:
    messages: list[LLMMessage]
    filestore: InMemoryFileStore


# Keyed by (user_name, product_id)
_state_store: dict[tuple[str, str], OrchestratorState] = defaultdict(
    lambda: OrchestratorState(
        messages=[],
        filestore=InMemoryFileStore()
    )
)


def load_state(user_name: str, product_id: str) -> OrchestratorState:
    """Retrieve the current state for a given user/product pair."""
    # TODO: make deep copy of state before passing it out
    return _state_store[(user_name, product_id)]


def save_state(user_name: str, product_id: str, state: OrchestratorState) -> None:
    """Persist the given state for a user/product pair."""
    _state_store[(user_name, product_id)] = state


async def baml_stream_and_collect_user_response(stream: BamlStream, stream_receiver) -> str:
    async def gen() -> AsyncIterator[str]:
        async for msg in stream:
            if type(msg) is CoderStream:
                update_status("Coder is writing the code...")
                # ignore coder messages because we don't want to stream them
                continue
            if type(msg) is ResponseToUserStream:
                # Stream message to user and collect the final message, then store the message into message history
                if not msg.response_to_user:
                    continue
                yield msg.response_to_user

    await stream_receiver(gen())

    return await stream.get_final_response()


@agent_task
async def edit_product(user_name: str, product_id: str, message: str,
                       coder_completed_callback,
                       stream_to_user_callback):
    # TODO: This duplication can be overcome by memoization, or passing state as param
    orchestrator_state = load_state(user_name, product_id)
    file_store = orchestrator_state.filestore
    update_status("Thinking...")
    orchestrator_state.messages.append(LLMMessage(role="user", content=message))
    response = await stream_user_response_or_coder(messages=orchestrator_state.messages, filestore=file_store)

    final_response = await baml_stream_and_collect_user_response(response, stream_to_user_callback)
    if isinstance(final_response, Coder):
        coder_response = await run_coder_agent(messages=orchestrator_state.messages, filestore=file_store)
        orchestrator_state.messages.append(LLMMessage(role="assistant", content=coder_response.content))
        await coder_completed_callback(user_name, product_id, file_store)
        update_status("The website is ready to be deployed. Use the 🚀 from the sidebar to deploy your website")
    elif isinstance(final_response, ResponseToUser):
        orchestrator_state.messages.append(LLMMessage(role="assistant", content=final_response.response_to_user))
    else:
        raise ValueError("Unexpected response type")


@agent_task
async def start_product(user_name: str, product_id: str, message: str,
                        coder_completed_callback, message_to_user_callback):
    t_agent = TemplateAgent(user_name, product_id)
    response = await t_agent.build_specification(message, message_to_user_callback)

    # We will only proceed to next step, if we have a website specification. Otherwise, wait for additional user input
    if isinstance(response, WebsiteSpecification):
        # TODO: This duplication can be overcome by memoization, or passing state as param, or using a class
        orchestrator_state = load_state(user_name, product_id)
        file_store = orchestrator_state.filestore
        new_spec = response.spec

        orchestrator_state.messages.append(LLMMessage(role="user", content=message))
        orchestrator_state.messages.append(LLMMessage(role="assistant", content=new_spec))
        orchestrator_state.messages.append(
            LLMMessage(role="user", content="Let's use this specification to build the website"))
        update_status("Coder is writing the code...")
        coder_response = await run_coder_agent(messages=orchestrator_state.messages, filestore=file_store)
        orchestrator_state.messages.append(LLMMessage(role="assistant", content=coder_response.content))
        await coder_completed_callback(user_name, product_id, file_store)

        update_status("The website is ready to be deployed. Use the 🚀 from the sidebar to deploy your website")


async def handle_user_message(user_name: str, product_id: str, message: str,
                              coder_completed_callback, stream_to_user_callback):
    orchestrator_state = load_state(user_name, product_id)
    file_store = orchestrator_state.filestore
    if file_store.file_exists(INDEX_FILE_NAME):
        await edit_product(user_name, product_id, message, coder_completed_callback, stream_to_user_callback)
    else:
        await start_product(user_name, product_id, message, coder_completed_callback, stream_to_user_callback)
