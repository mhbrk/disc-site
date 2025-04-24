import asyncio
import logging
import os
from typing import NotRequired

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import START, END
from langgraph.graph import StateGraph, MessagesState
from langgraph.types import interrupt, Command

from common.model import Message
from instruction_reader import get_instructions


# Define the structure of our state
class State(MessagesState):
    prompt: NotRequired[str]


logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)


class BuilderAgent:

    def __init__(self):
        self.system_prompt = get_instructions("builder_agent_system_prompt")

        # Initialize model with tools
        self.model = ChatOpenAI(model="gpt-4.1", temperature=0)

        checkpointer = MemorySaver()

        # Create a state graph
        graph = StateGraph(state_schema=State)

        # Add the agent and tools nodes
        graph.add_node("agent", self.agent)
        graph.add_node("extract_prompt", self.extract_prompt)
        graph.add_node("get_user_input", self.get_user_input)

        # Define transitions: agent → tools, then loop back to agent
        graph.add_edge(START, "agent")
        graph.add_conditional_edges("agent", self.is_final_prompt, {True: "extract_prompt", False: "get_user_input"})
        graph.add_edge("get_user_input", "agent")
        graph.add_edge("extract_prompt", END)

        self.graph = graph
        self.app = graph.compile(checkpointer=checkpointer)

        self.final_state: State | None = None

    def is_final_prompt(self, state: State) -> bool:
        if len(state["messages"]) > 1:
            message = state["messages"][-1].content
            split_message = message.split("::final prompt result::")

            if len(split_message) > 1 and split_message[1]:
                return True
        return False

    def get_user_input(self, state: State) -> State:
        question = state["messages"][-1].content
        answer: Message = interrupt(question)
        return {"messages": [{"role": answer.role, "content": answer.parts[0].text}]}

    def extract_prompt(self, state: State) -> State:
        message = state["messages"][-1].content
        split_message = message.split("::final prompt result::")
        prompt = ""
        if len(split_message) > 1:
            prompt = split_message[1]
        return {"prompt": prompt}

    async def agent(self, state: State) -> State:
        system_message = SystemMessage(content=self.system_prompt)
        response = await self.model.ainvoke([system_message] + state["messages"])
        return {"messages": [response]}

    def visualize(self):
        with open("builder_agent.png", "wb") as file:
            file.write(self.app.get_graph().draw_mermaid_png())

    def stream(self, session_id: str, user_input: Message):
        config = RunnableConfig(recursion_limit=100, configurable={"thread_id": session_id})
        logger.info(f"Streaming builder agent with user input: {user_input}")
        for event in self.app.stream({"messages": [{"role": user_input.role, "content": user_input.parts[0].text}]},
                                     config, stream_mode="values"):
            event['messages'][-1].pretty_print()
            self.final_state = event

    async def invoke(self, session_id: str, user_input: Message):
        config = RunnableConfig(recursion_limit=100, configurable={"thread_id": session_id})
        # if the agent is waiting for user input
        if self.is_waiting_for_user_input(config):
            await self.app.ainvoke(Command(resume=user_input), config)
        else:
            # This happens in only with the first task request, if task is being continued this will not work
            logger.info(f"Invoking builder agent with user input: {user_input}")
            await self.app.ainvoke({"messages": [{"role": user_input.role, "content": user_input.parts[0].text}]},
                                   config)
        return self.get_agent_response(config)

    def is_waiting_for_user_input(self, config: dict):
        state_snapshot = self.app.get_state(config)
        next_node_tuple = state_snapshot.next

        if len(next_node_tuple) > 0:
            return next_node_tuple[0] == "get_user_input"
        return False

    def get_agent_response(self, config):
        # TODO: use aget_state
        current_state = self.app.get_state(config)
        # check if an interrupt was triggered by get_user_input node
        if self.is_waiting_for_user_input(config):
            return {
                "is_task_complete": False,
                "require_user_input": True,
                "content": current_state.values["messages"][-1].content
            }
        elif current_state.values["prompt"]:
            return {
                "is_task_complete": True,
                "require_user_input": False,
                "content": current_state.values["prompt"]
            }

        return {
            "is_task_complete": False,
            "require_user_input": True,
            "content": "We are unable to process your request at the moment. Please try again.",
        }

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]


if os.environ.get("OPENAI_API_KEY") is None:
    load_dotenv()

agent = BuilderAgent()

if __name__ == "__main__":
    load_dotenv()


    async def run_agent():
        await agent.invoke("user-1-session-1",
                           "Create a website for my 18th birthday party")

        while True:
            agent_response = await agent.invoke("user-1-session-1",
                                                "Just do what you think is best.")
            if not agent.is_waiting_for_user_input({"configurable": {"thread_id": "user-1-session-1"}}):
                break

        print(agent_response["content"])


    asyncio.run(run_agent())
