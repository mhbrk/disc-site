import datetime
import logging
from typing import Any, Dict, AsyncIterable

from langchain_community.tools import TavilySearchResults
from langchain_core.messages import trim_messages, HumanMessage
from langchain_core.messages.utils import count_tokens_approximately
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from langgraph.prebuilt.chat_agent_executor import AgentState
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .generate_image import generate_image
from .instruction_reader import get_instructions

logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)

memory = MemorySaver()


def extract_html_content(content: str):
    split_message = content.split("::final html output::")
    if len(split_message) > 1:
        return split_message[1]
    else:
        return ""


def pre_model_hook(state):
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
    SYSTEM_INSTRUCTION = get_instructions("generator_system_prompt")

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

        search_tool = TavilySearchResults(max_results=5, include_images=True)
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

        self.model = ChatOpenAI(model="gpt-4.1", temperature=0)
        self.tools = base_tools + mcp_tools
        self.graph = create_react_agent(
            self.model,
            tools=self.tools,
            state_schema=GeneratorState,
            pre_model_hook=pre_model_hook,
            checkpointer=memory,
            prompt=self.SYSTEM_INSTRUCTION
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

    async def stream(self, query: str, user_name: str, session_id: str) -> AsyncIterable[Dict[str, Any]]:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # TODO: username needs to be used as a static parameter to the tool call
        #  For this need to redo the generator agent using custom graph or using baml
        inputs = {
            "messages": [("user", f"Your session id is: {session_id}."),
                         ("user", f"The user name for tool use is: {user_name}."),
                         ("user", f"Current time is: {current_time}"),
                         ("user", query)],
            "specification": query
        }

        config = {"configurable": {"thread_id": session_id}}

        async for mode, data in self.graph.astream(inputs, config, stream_mode=["messages", "values"]):
            if mode == "messages":
                chunk, metadata = data
                if metadata["langgraph_node"] == "agent" and chunk.content:
                    yield {
                        "is_task_complete": False,
                        "require_user_input": False,
                        "content": chunk.content,
                    }
            if mode == "values":
                logger.info(data["messages"][-1].pretty_repr())

        yield self.get_agent_response(config)

    async def editing_stream(self, query: str, user_name: str, session_id: str) -> AsyncIterable[Dict[str, Any]]:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # TODO: username needs to be used as a static parameter to the tool call
        #  For this need to redo the generator agent using custom graph or using baml
        inputs = {"messages": [("user", f"Your session id is: {session_id}."),
                               ("user", f"The user name for tool use is: {user_name}."),
                               ("user", f"Current time is: {current_time}"),
                               ("user", f"Current specification is: {self.get_last_specification(session_id)}"),
                               ("user", query)],
                  }

        config = {"configurable": {"thread_id": session_id}}

        async for mode, data in self.graph.astream(inputs, config, stream_mode=["messages", "values"]):
            if mode == "messages":
                chunk, metadata = data
                if metadata["langgraph_node"] == "agent" and chunk.content:
                    yield {
                        "is_task_complete": False,
                        "require_user_input": False,
                        "content": chunk.content,
                    }
            if mode == "values":
                logger.info(data["messages"][-1].pretty_repr())

        yield self.get_agent_response(config)

    def get_last_specification(self, session_id):
        config = {"configurable": {"thread_id": session_id}}
        current_state = self.graph.get_state(config)
        return current_state.values.get('specification')

    def get_last_html(self, session_id):
        config = {"configurable": {"thread_id": session_id}}
        current_state = self.graph.get_state(config)
        last_message = current_state.values.get('messages')[-1]
        extracted_text = extract_html_content(last_message.content)
        return extracted_text

    def set_last_html(self, session_id, html_output):
        config = {"configurable": {"thread_id": session_id}}
        self.graph.update_state(config,
                                {"messages": [("user", f"::final html output::{html_output}::final html output::")]})

    def get_agent_response(self, config):
        current_state = self.graph.get_state(config)
        last_message = current_state.values.get('messages')[-1]
        html_output = extract_html_content(last_message.content)
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
