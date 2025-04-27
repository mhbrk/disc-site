import logging
from typing import Any, Dict, AsyncIterable, Literal

from langchain_community.tools import TavilySearchResults
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from generator_agent.app.generate_image import generate_image
from instruction_reader import get_instructions

logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)

memory = MemorySaver()

class ResponseFormat(BaseModel):
    """Respond to the user in this format."""
    status: Literal["input_required", "completed", "error"] = "input_required"
    html_output: str = Field(description="The HTML content to be rendered as the final output.")


class HTMLAgent:
    SYSTEM_INSTRUCTION = get_instructions("generator_system_prompt")

    def __init__(self):
        search_tool = TavilySearchResults(
            max_results=5,
            include_answer=True,
            include_raw_content=True,
            include_images=True,
        )

        self.model = ChatOpenAI(model="gpt-4.1", temperature=0)
        self.tools = [generate_image, search_tool]

        self.graph = create_react_agent(
            self.model, tools=self.tools, checkpointer=memory, prompt=self.SYSTEM_INSTRUCTION,
            response_format=ResponseFormat
        )

    def invoke(self, query, sessionId):
        config = {"configurable": {"thread_id": sessionId}}
        self.graph.invoke({"messages": [("user", query)]}, config)
        return self.get_agent_response(config)

    async def stream(self, query: str, session_id: str, task_id: str) -> AsyncIterable[Dict[str, Any]]:
        inputs = {"messages": [("user", f"Your session id is: {session_id}."),
                               ("user", f"Your task id is: {task_id}."),
                               ("user", query)]}

        config = {"configurable": {"thread_id": session_id}}

        async for mode, data  in self.graph.astream(inputs, config, stream_mode=["messages", "values"]):
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

    def get_agent_response(self, config):
        current_state = self.graph.get_state(config)
        structured_response = current_state.values.get('structured_response')
        if structured_response and isinstance(structured_response, ResponseFormat):
            if structured_response.status == "input_required":
                return {
                    "is_task_complete": False,
                    "require_user_input": True,
                    "content": structured_response.message
                }
            elif structured_response.status == "error":
                return {
                    "is_task_complete": False,
                    "require_user_input": True,
                    "content": structured_response.message
                }
            elif structured_response.status == "completed":
                return {
                    "is_task_complete": True,
                    "require_user_input": False,
                    "content": structured_response.html_output
                }

        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "We are unable to process your request at the moment. Please try again.",
        }

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]


agent = HTMLAgent()
