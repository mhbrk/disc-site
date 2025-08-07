import asyncio
import datetime
import logging
import os

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage, trim_messages, HumanMessage
from langchain_core.messages.utils import count_tokens_approximately
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import START, END
from langgraph.graph import StateGraph, MessagesState
from langgraph.types import interrupt, Command

from breba_app.agent_model import Message
from breba_app.storage import list_files_in_private
from .instruction_reader import get_instructions


class State(MessagesState):
    """
    State for the builder agent.
    messages: list[str] - to keep track of the conversation
    prompt: str - the prompt to run
    """
    prompt: str | None

    session_id: str
    user_name: str


logging.basicConfig(level=logging.INFO, )
logger = logging.getLogger(__name__)


class BuilderAgent:

    def __init__(self):
        self.model = ChatOpenAI(model="gpt-4.1", temperature=0)

        # Create a checkpointer, could use MongoDB checkpointer in the future
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
        """
        Checks if agent has decided to produce final prompt in its last message.
        :param state: agent state that contains messages
        :return: boolean indicating if agent has decided to produce final prompt in the last message
        """
        if len(state["messages"]) > 1:
            message = state["messages"][-1].content
            split_message = message.split("::final website specification::")

            if len(split_message) > 1 and split_message[1]:
                return True
        return False

    def get_user_input(self, state: State) -> State:
        """
        Use interrupt mechanism from langgraph. The client will need to re-invoke the agent to continue
        :param state: state of the agent just before the interrupt.
        :return: state updated with the message from the client.
        """
        question = state["messages"][-1].content
        answer: Message = interrupt(question)
        return {"messages": [{"role": answer.role, "content": answer.parts[0].text}]}

    def extract_prompt(self, state: State) -> State:
        """
        This is a shortcut to structured output without using an extra LLM invokation.
        """
        last_message = state["messages"][-1]
        message = last_message.content
        split_message = message.split("::final website specification::")
        prompt = ""
        if len(split_message) > 1:
            prompt = split_message[1]
            # By setting id we are making sure that we replace the last message
            last_message = {"id": last_message.id, "role": "user", "content": f"This the full spec for my site: {prompt}"}

        return {"prompt": prompt, "messages": [last_message]}

    async def agent(self, state: State, config: RunnableConfig) -> State:
        # TODO: use callback or class to get files, probably usersessioncontext class to get userid, user time, and zone

        trimmed_messages = trim_messages(
            state["messages"],
            strategy="last",
            token_counter=count_tokens_approximately,
            max_tokens=30000,
            start_on=[HumanMessage],
            include_system=True,
        )

        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        system_message = SystemMessage(content=get_instructions("builder_agent_system_prompt",
                                                                files=list_files_in_private(state["user_name"],
                                                                                            config['configurable'][
                                                                                                "thread_id"]),
                                                                current_time=current_time))
        response = await self.model.ainvoke([system_message] + trimmed_messages)
        return {"messages": [response]}

    def visualize(self):
        with open("builder_agent.png", "wb") as file:
            file.write(self.app.get_graph().draw_mermaid_png())

    def stream(self, session_id: str, user_input: Message):
        # TODO: this is not used and outdated
        config = RunnableConfig(recursion_limit=100, configurable={"thread_id": session_id})
        logger.info(f"Streaming builder agent with user input: {user_input}")
        for event in self.app.stream({"messages": [{"role": user_input.role, "content": user_input.parts[0].text}]},
                                     config, stream_mode="values"):
            event['messages'][-1].pretty_print()
            self.final_state = event

    async def invoke(self, user_name: str, session_id: str, user_input: Message):
        config = RunnableConfig(recursion_limit=100, configurable={"thread_id": session_id})
        # Preset the state
        await self.app.aupdate_state(config, {"user_name": user_name}, as_node="extract_prompt")
        # if the agent is waiting for user input
        if self.is_waiting_for_user_input(config):
            await self.app.ainvoke(Command(resume=user_input), config)
        else:
            # This happens in only with the first task request, if task is being continued this will not work
            logger.info(f"Invoking builder agent with user input: {user_input}")
            await self.app.ainvoke({"messages": [{"role": user_input.role, "content": user_input.parts[0].text}]},
                                   config)
        return await self.get_agent_response(config)

    def is_waiting_for_user_input(self, config: dict):
        """
        Helper function to check if the agent is waiting for user input, to facilitate human in the loop
        :param config: agent config used to get state.
        :return: True, if the next agent node is "get_user_input" indicate interrupt was triggered.
                 False, otherwise.
        """
        state_snapshot = self.app.get_state(config)
        next_node_tuple = state_snapshot.next

        if len(next_node_tuple) > 0:
            return next_node_tuple[0] == "get_user_input"
        return False

    async def get_agent_response(self, config):
        current_state = await self.app.aget_state(config)
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

    async def set_agent_prompt(self, session_id, prompt: str):
        config = RunnableConfig(configurable={"thread_id": session_id})
        # Must add to messages in order to be able to continue conversation
        await self.app.aupdate_state(config, {"prompt": prompt, "messages": [
            ("user", f"Load the following spec: {prompt}"),
            ("ai", f"::final website specification::\n{prompt}\n::final website specification::")]}, as_node="extract_prompt")


if os.environ.get("OPENAI_API_KEY") is None:
    load_dotenv()

agent = BuilderAgent()

if __name__ == "__main__":
    load_dotenv()


    async def run_agent():
        session_id = "user-1-session-1"
        await agent.invoke(session_id, "Create a website for my 18th birthday party")

        while True:
            agent_response = await agent.invoke(session_id, "Just do what you think is best.")
            if not agent.is_waiting_for_user_input({"configurable": {"thread_id": session_id}}):
                break

        print(agent_response["content"])


    asyncio.run(run_agent())
