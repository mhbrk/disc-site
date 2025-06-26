import asyncio

import chainlit as cl
from chainlit import Message

from auth import verify_password
from common.storage import save_file_to_private, save_image_file_to_private, upload_site, load_template, read_spec_text, \
    read_index_html
from models.user import User
from orchestrator import get_generator_response, to_builder, update_builder_spec, set_generator_response


async def builder_completed(payload: str):
    session_id = cl.user_session.get("id")
    user_name = cl.user_session.get("user").identifier

    save_file_to_private(user_name, session_id, "spec.txt", payload.encode("utf-8"), "text/plain")
    builder_message = {"method": "to_builder", "body": payload}
    await cl.send_window_message(builder_message)


async def generator_completed():
    session_id = cl.user_session.get("id")
    user_name = cl.user_session.get("user").identifier

    html = get_generator_response(session_id)

    save_file_to_private(user_name, session_id, "index.html", html, "text/html")

    await cl.Message(
        content="The website is ready to be deployed. Use the 🚀 from the sidebar to deploy your website").send()


async def process_generator_message(message: str):
    if message == "__completed__":
        await generator_completed()
    generator_message = {"method": "to_generator", "body": message}
    await cl.send_window_message(generator_message)


@cl.action_callback("action_button")
async def on_action(action: cl.Action):
    print(action.payload)


async def ask_user(message: str):
    await cl.Message(content=message).send()


@cl.on_chat_start
async def main():
    await cl.Message(
        content="Hello, I'm here to assist you with building your website. We can build it together one step at a time,"
                " or you can give me the full specification, and I will have it built.").send()


@cl.on_window_message
async def window_message(message: str | dict):
    method = "user_message"
    if isinstance(message, dict):
        method = message.get("method")

    session_id = cl.user_session.get("id")
    user_name = cl.user_session.get("user").identifier

    if method == "to_builder":
        await to_builder(user_name, session_id, message.get("body", "INVALID REQEUST, something went wrong"),
                         builder_completed,
                         ask_user, process_generator_message)
    elif method == "load_template":
        load_template(user_name, session_id, message.get("body"))
        spec = read_spec_text(user_name, session_id)
        product = read_index_html(user_name, session_id)
        set_generator_response(session_id, product)

        await process_generator_message(product)

        await asyncio.gather(update_builder_spec(session_id, spec), builder_completed(spec),
                             process_generator_message("__completed__"))
    elif method == "deploy":
        site_name = message.get("body")
        url = upload_site(user_name, session_id, site_name)
        message_text = f"Deployed your website to: {url}"
        await asyncio.gather(cl.Message(content=message_text).send(),
                             cl.send_window_message({"method": "deploy_status", "body": message_text}))
    else:
        # TODO: remove this, it is replaced by the "ask_user" function callback
        await cl.Message(content=message).send()


@cl.on_message
async def respond(message: Message):
    session_id = cl.user_session.get("id")
    user_name = cl.user_session.get("user").identifier

    if len(message.elements) > 0:
        # This happens when we are uploading a file from the chat window
        blob_image_path = save_image_file_to_private(user_name, session_id, message.elements[0].name,
                                                     message.elements[0].path,
                                                     message.content)
        # TODO: remove this when using CDN
        image_path_for_preview = blob_image_path.replace("images/", f"images/{session_id}/")
        message.content = f"Given: ./{image_path_for_preview} \n {message.content}"
    await to_builder(user_name, session_id, message.content, builder_completed, ask_user, process_generator_message)


@cl.password_auth_callback
async def auth_callback(username: str, password: str):
    user = await User.find_one(User.username == username)

    if verify_password(password, user.password_hash):
        return cl.User(
            identifier=username, metadata={"role": "user", "provider": "credentials"}
        )
    else:
        return None
