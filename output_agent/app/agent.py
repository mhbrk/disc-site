from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

from typing import Any, Dict, AsyncIterable, Literal
from pydantic import BaseModel

memory = MemorySaver()


@tool
def generate_image(prompt: str):
    """This tool starts to generate images. It will return image path, and then start to generate the image.

    Args:
        prompt: The prompt to generate the image.

    Returns:
        The image path.
    """
    return "https://en.wikipedia.org/wiki/Image#/media/File:Image_created_with_a_mobile_phone.png"


class ResponseFormat(BaseModel):
    """Respond to the user in this format."""
    status: Literal["input_required", "completed", "error"] = "input_required"
    message: str


class HTMLAgent:
    SYSTEM_INSTRUCTION = (
        "You are a web server, serving HTML web pages. Do not use markdown for formatting. "
        "All output must be in HTML format and will be displayed to an end user. "
        "You need to start with doctype and html tags and provide the entire page."
        "Do not attempt to answer unrelated questions or use tools for other purposes."
        "Set response status to input_required if the user needs to provide more information."
        "Set response status to error if there is an error while processing the request."
        "Set response status to completed if the request is complete."
    )

    def __init__(self):
        self.model = ChatOpenAI(model="gpt-4o", temperature=0)
        self.tools = [generate_image]

        self.graph = create_react_agent(
            self.model, tools=self.tools, checkpointer=memory, prompt=self.SYSTEM_INSTRUCTION,
            response_format=ResponseFormat
        )

    def invoke(self, query, sessionId):
        config = {"configurable": {"thread_id": sessionId}}
        self.graph.invoke({"messages": [("user", query)]}, config)
        return self.get_agent_response(config)

    async def stream(self, query, sessionId) -> AsyncIterable[Dict[str, Any]]:
        inputs = {"messages": [("user", query)]}
        config = {"configurable": {"thread_id": sessionId}}

        async for message_chunk, metadata in self.graph.astream(inputs, config, stream_mode="messages"):
            yield {
                "is_task_complete": False,
                "require_user_input": False,
                "content": message_chunk.content,
            }

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
                    "content": structured_response.message
                }

        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "We are unable to process your request at the moment. Please try again.",
        }

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]


agent = HTMLAgent()
