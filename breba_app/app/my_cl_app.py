import uuid

import chainlit as cl
from chainlit import Message
from chainlit.types import CommandDict

from site_upload import upload_site
from orchestrator import to_builder

task_id: str | None = None


async def builder_completed(payload: str):
    builder_message = {"method": "to_builder", "body": payload}
    await cl.send_window_message(builder_message)


async def process_generator_message(message: str):
    if message == "__completed__":
        await cl.Message(content="The website is ready to be deployed. Use the /Deploy my-site to deploy your website as my-site.").send()
    generator_message = {"method": "to_generator", "body": message}
    await cl.send_window_message(generator_message)


@cl.action_callback("action_button")
async def on_action(action: cl.Action):
    print(action.payload)


async def ask_user(message: str):
    await cl.Message(content=message).send()


@cl.on_chat_start
async def main():
    global task_id
    task_id = f"task-{uuid.uuid4().hex}"

    deploy_cmd: CommandDict = {"id": "Deploy", "icon": "globe", "description": "Deploy the website. type name of site after the command"}
    commands = [deploy_cmd]
    await cl.context.emitter.set_commands(commands)

    await cl.Message(
        content="Hello, I'm here to assist you with building your website. We can build it together one step at a time,"
                " or you can give me the full specification, and I will have it built.").send()


@cl.on_window_message
async def window_message(message: str | dict):
    method = "user_message"
    if isinstance(message, dict):
        method = message.get("method")

    session_id = "user-1-session-1"  # hardcoded for now
    if method == "to_builder":
        await to_builder(session_id, message.get("body", "INVALID REQEUST, something went wrong"), builder_completed,
                         ask_user, process_generator_message)
    else:
        # TODO: remove this, it is replaced by the "ask_user" function callback
        await cl.Message(content=message).send()


@cl.on_message
async def respond(message: Message):
    if message.command == "Deploy":
        site_name = message.content
        if not site_name:
            await cl.Message(content="Please provide a name for your site.").send()
            return

        upload_site(f"sites/{site_name}", site_name)
        await cl.Message(content="Deploying your website...").send()
    else:
        # session_id = cl.user_session.get("id")
        session_id = "user-1-session-1"  # hardcoded for now
        await to_builder(session_id, message.content, builder_completed, ask_user, process_generator_message)
