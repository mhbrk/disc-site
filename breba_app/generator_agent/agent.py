import asyncio
import datetime
import logging
from typing import Any, Dict, AsyncIterable

from langchain.agents.middleware import before_model
from langchain_core.callbacks import UsageMetadataCallbackHandler
from langchain_core.messages import trim_messages, HumanMessage
from langchain_core.messages.utils import count_tokens_approximately
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.checkpoint.memory import MemorySaver
from langchain.agents import AgentState, create_agent
from langgraph.runtime import Runtime
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from breba_app.diff import get_diff
from .diffing import diff_text
from .generate_image import generate_image
from .instruction_reader import get_instructions
from .static_html_example_messages import html_best_practices
from ..controllers.usage_controller import report_usage

logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)

memory = MemorySaver()

HTML_OUTPUT_MARKER = "::final html output::"


def extract_html_content(content: str):
    split_message = content.split(HTML_OUTPUT_MARKER)
    if len(split_message) > 1:
        return split_message[1].strip()
    else:
        return ""


@before_model
def pre_model_hook(state, runtime: Runtime):
    trimmed_messages = trim_messages(
        state["messages"],
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=40000,
        start_on=[HumanMessage],
        include_system=True,
    )
    # You can return updated messages either under `llm_input_messages` or
    # `messages` key (see the note below)
    return {"llm_input_messages": trimmed_messages}


class GeneratorState(AgentState):
    specification: str


class HTMLAgent:
    SYSTEM_INSTRUCTION = get_instructions("generator_system_prompt", best_practices=html_best_practices)

    def __init__(self):
        self.model = None
        self.tools = None
        self.graph = None
        self._initialized = False
        self._mcp_session = None
        self._mcp_stream_ctx = None

    async def ensure_initialized(self, pat: str):
        if self._initialized:
            return

        search_tool = TavilySearch(max_results=5, include_images=True)
        base_tools = [generate_image, search_tool]

        headers = {
            "Authorization": f"Bearer {pat}",
            "X-MCP-Toolsets": "issues,users,pull_requests,orgs,repos",
            "X-MCP-Readonly": "true"
        }

        self._mcp_stream_ctx = streamablehttp_client(
            url="https://api.githubcopilot.com/mcp/", headers=headers
        )
        read, write, session_id_callback = await self._mcp_stream_ctx.__aenter__()
        session = ClientSession(read, write)
        await session.__aenter__()

        await session.initialize()
        mcp_tools = await load_mcp_tools(session)

        self.model = ChatOpenAI(model="gpt-5.1", reasoning={"effort": "low"}, verbosity="low", use_responses_api=True)
        # self.tools = base_tools + mcp_tools
        self.tools = base_tools
        self.graph = create_agent(
            self.model,
            tools=self.tools,
            state_schema=GeneratorState,
            middleware=[pre_model_hook],
            checkpointer=memory,
            system_prompt=self.SYSTEM_INSTRUCTION
        )

        self._mcp_session = session
        self._initialized = True

    async def close(self):
        if self._mcp_session:
            await self._mcp_session.__aexit__(None, None, None)
        if self._mcp_stream_ctx:
            await self._mcp_stream_ctx.__aexit__(None, None, None)

    def invoke(self, query, session_id):
        # TODO: this is unused and outdated?
        config = {"configurable": {"thread_id": session_id}}
        self.graph.invoke({"messages": [("user", query)]}, config)
        return self.get_agent_response(config)

    async def stream(self, spec: str, user_name: str, session_id: str) -> AsyncIterable[Dict[str, Any]]:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # TODO: username needs to be used as a static parameter to the tool call
        #  For this need to redo the generator agent using custom graph or using baml
        inputs = {
            "messages": [("user", f"Your session id is: {session_id}."),
                         ("user", f"The user name for tool use is: {user_name}."),
                         ("user", f"Current time is: {current_time}"),
                         ("user", spec)],
            "specification": spec
        }

        usage_callback = UsageMetadataCallbackHandler()
        config = {"configurable": {"thread_id": session_id}, "callbacks": [usage_callback]}

        async for chunk, metadata in self.graph.astream(inputs, config, stream_mode="messages"):
            text = None
            if metadata["langgraph_node"] == "model" and chunk.content:
                if isinstance(chunk.content, str):
                    text = chunk.content
                elif isinstance(chunk.content, list):
                    # filter out everything except type == text
                    text_list = [item.get("text", "") for item in chunk.content if item["type"] == "text"]
                    text = "".join(text_list)
                if text:
                    yield {
                        "is_task_complete": False,
                        "require_user_input": False,
                        "content": text,
                }

        # TODO: This should be an Agent Bus event
        asyncio.create_task(report_usage(user_name, session_id, usage_callback.usage_metadata))
        yield self.get_agent_response(config)

    def is_spec_similar(self, current_spec: str, new_spec: str) -> bool:
        new_spec_lines = new_spec.splitlines()
        current_spec_lines = current_spec.splitlines()
        diff_count = len(set(new_spec_lines) ^ set(current_spec_lines))
        relative_diff = diff_count / max(len(set(current_spec_lines) | set(new_spec_lines)), 1)
        return relative_diff < 0.5

    async def diffing_spec_update(self, spec: str, user_name: str, product_id: str):
        """
        This method is used to update the specification.
        """
        logger.info("Generator diffing spec update")
        current_spec = self.get_last_specification(product_id)

        if not current_spec:
            logger.info("No current spec found. This is not supported for a diffing update.")
            raise Exception("No current spec found. This is not supported for a diffing update.")
        if current_spec == spec:
            logger.info("Provided spec is the same as the current spec. This is not supported for a diffing update.")
            raise Exception(
                "Provided spec is the same as the current spec. This is not supported for a diffing update.")

        diff = get_diff(current_spec, spec)
        if not self.is_spec_similar(current_spec, spec):
            # when there are lots of changes to the spec, we will stream the full spec update
            logger.info("Spec diff is too big. You have to treat it like a new specification")
            raise Exception(
                f"Spec diff is too big.")
        else:
            try:
                query = f"I changed the spec given the following diff:\n{diff}"
                update = await self.diffing_update(user_name, product_id, query)
                self.set_spec(product_id, spec)
                # We will just stream the entire spec
                self.set_last_html(product_id, update)
                config = {"configurable": {"thread_id": product_id}}
                yield self.get_agent_response(config)
            except Exception as e:
                logger.error(f"Failed to diff spec: {e}")
                raise e

    async def diffing_update(self, user_name: str, product_id: str, query: str, ):
        """
        This method is used to update only the parts of the html that need to be updated.
        :return: modified html
        :raises: Exception if the diff is too long, or malformed
        """
        logger.info("Generator diffing update")
        html = self.get_last_html(product_id)
        # TODO: This currently doesn't support tool calling and can only handle simple html changes
        modified = await diff_text(user_name, product_id, html, query)
        logger.info(f"Diff was successfully applied")
        self.set_last_html(product_id, modified)
        # TODO: this violates the interface because the agent returns text instead of agent response
        return modified

    async def editing_stream(self, query: str, user_name: str, session_id: str) -> AsyncIterable[Dict[str, Any]]:
        """
        Stream inline editing query. The input is not a full specification, but a query to be applied to the current
        specification. This method is used when diffing update fails and we will generate the full html for the website.
        """
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # TODO: username needs to be used as a static parameter to the tool call
        #  For this need to redo the generator agent using custom graph or using baml
        # The difference between editing and regular stream is that this function gets the last specification to work with
        # that last specification was set by the original stream call
        inputs = {"messages": [("user", f"Current specification is: {self.get_last_specification(session_id)}"),
                               ("assistant", f"{HTML_OUTPUT_MARKER}\n{self.get_last_html(session_id)}\n"
                                             f"{HTML_OUTPUT_MARKER}"),
                               ("system", f"Your session id is: {session_id}.\n"
                                          f"The user name for tool use is: {user_name}.\n"
                                          f"Current time is: {current_time}"),
                               ("user", query)],
                  }
        usage_callback = UsageMetadataCallbackHandler()
        config = {"configurable": {"thread_id": session_id}, "callbacks": [usage_callback]}

        async for mode, data in self.graph.astream(inputs, config, stream_mode=["messages", "values"]):
            if mode == "messages":
                chunk, metadata = data
                if metadata["langgraph_node"] == "agent" and chunk.content:
                    yield {
                        "is_task_complete": False,
                        "require_user_input": False,
                        "content": chunk.content,
                    }

        # TODO: This should be an Agent Bus event
        asyncio.create_task(report_usage(user_name, session_id, usage_callback.usage_metadata))
        yield self.get_agent_response(config)

    def set_spec(self, session_id: str, spec: str):
        config = {"configurable": {"thread_id": session_id}}
        self.graph.update_state(config, {"specification": spec})

    def get_last_specification(self, session_id):
        config = {"configurable": {"thread_id": session_id}}
        current_state = self.graph.get_state(config)
        return current_state.values.get('specification')

    def get_last_html(self, session_id):
        config = {"configurable": {"thread_id": session_id}}
        current_state = self.graph.get_state(config)
        messages = current_state.values.get('messages')
        if messages:
            last_message = messages[-1]
            extracted_text = extract_html_content(last_message.text)
            return extracted_text
        else:
            return None

    def set_last_html(self, session_id, html_output):
        config = {"configurable": {"thread_id": session_id}}
        self.graph.update_state(config,
                                {"messages": [("user", f"{HTML_OUTPUT_MARKER}{html_output}{HTML_OUTPUT_MARKER}")]})

    def get_agent_response(self, config):
        current_state = self.graph.get_state(config)
        last_message = current_state.values.get('messages')[-1]
        html_output = extract_html_content(last_message.text)
        if html_output:
            return {
                "is_task_complete": True,
                "require_user_input": False,
                "content": html_output
            }

        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "We are unable to process your request at the moment. Please try again.",
        }


agent = HTMLAgent()
