import asyncio
from typing import AsyncIterator

import chainlit as cl
from beanie import SortDirection, PydanticObjectId
from bson import DBRef
from chainlit import Message

import breba_app.ui_bus as ui_bus
from auth import verify_password
from breba_app.config import SPEC_FILE_NAME, INDEX_FILE_NAME
from breba_app.controllers.product_controller import delete_product
from breba_app.events.bus import HandleContext, Consumer, event_bus
from breba_app.events.coder_completed import CoderCompleted
from breba_app.filesystem import InMemoryFileStore, FileWrite
from breba_app.models.deployment import Deployment
from breba_app.models.product import Product, create_or_update_product_for, create_blank_product_for, set_product_active
from breba_app.models.user import User
from breba_app.orchestrator import handle_user_message, save_state, OrchestratorState, start_product
from breba_app.storage import has_cloud_storage, list_versions, get_active_version, set_version_active, \
    read_all_files_in_memory, save_files
from breba_app.template_agent.product_types.landing_page import landing_page_instructions, \
    landing_page_follow_up_questions
from breba_app.ui_bus import update_products_list, update_versions_list, update_follow_up_questions_list
from controllers.deployment_controller import run_deployment
from llm_utils import get_product_name
from storage import save_image_file_to_private, get_public_url

PRODUCT_NAME_PLACEHOLDER = "Unnamed Product"


class ProductNameAssignmentConsumer(Consumer):
    def __init__(self, user_name: str, product_id: str):
        self.id = f"product_name_assignment_{user_name}_{product_id}"
        super().__init__()

    async def handle(self, ctx: HandleContext, event: CoderCompleted) -> None:
        product_name = await get_product_name(event.filestore.read_text(INDEX_FILE_NAME))
        product = await create_or_update_product_for(event.user_name, event.product_id, product_name)
        cl.user_session.set("product_name", product.name)
        await ui_bus.update_product_name(event.product_id, product.name)
        await ctx.unsubscribe_self()


async def ask_user_streaming(token_stream: AsyncIterator[str] | str):
    if isinstance(token_stream, str):
        msg = cl.Message(content=token_stream)
    else:
        msg = cl.Message(content="")

        # Stream each token into it as they arrive
        async for chunk in token_stream:
            if not chunk:
                continue
            await msg.stream_token(chunk, is_sequence=True)

    # Send the fully streamed message once complete
    if msg.content:
        await msg.send()


async def populate_from_cloud_storage(user_name: str, session_id: str):
    in_memory_store = await read_all_files_in_memory(user_name, session_id)

    save_state(user_name, session_id, OrchestratorState(messages=[], filestore=in_memory_store))

    spec = ""
    if in_memory_store.file_exists(SPEC_FILE_NAME):
        spec = in_memory_store.read_text(SPEC_FILE_NAME)
    product = in_memory_store.read_text(INDEX_FILE_NAME)

    await asyncio.gather(
        ui_bus.send_specification_to_ui(spec),
        ui_bus.send_index_html_to_ui(product)
    )


async def coder_completed(user_name: str, product_id: str, file_store: InMemoryFileStore):
    """
    This is called when the coder agent is done.
    It will update the UI with the updated files
    It will also persist the files to the cloud storage

    :param user_name: used to identify the session
    :param product_id: used to identify the session
    :param file_store the in memory file store provided by the coder agent
    """
    spec = ""
    if file_store.file_exists("spec.txt"):
        spec = file_store.read_text("spec.txt")
    # TODO: This should be the file being viewed by the user.
    html = file_store.read_text("index.html")
    await asyncio.gather(
        ui_bus.send_specification_to_ui(spec),
        ui_bus.send_index_html_to_ui(html)
    )

    files_to_save: list[FileWrite] = list(file_store.snapshot().values())
    new_version = await save_files(user_name, product_id, files_to_save)
    versions = await list_versions(user_name, product_id)
    await update_versions_list(versions, new_version)
    # TODO: This is just the first step. This entire callback should go away once event bus is work. That is the purpose of the event bus.
    await event_bus.emit(CoderCompleted(user_name=user_name, product_id=product_id, filestore=file_store))


async def update_deployments_list(product_id: PydanticObjectId):
    deployments = await Deployment.find(Deployment.product == DBRef("products", product_id)).sort(
        [("deployed_at", SortDirection.DESCENDING)]).to_list()

    if not deployments:
        return  # Nothing do here

    deployments_list = [{"id": str(deployment.id), "deployment_id": deployment.deployment_id,
                         "url": get_public_url(deployment.deployment_id)} for deployment in deployments]
    await cl.send_window_message({"method": "update_deployments_list", "body": deployments_list})


@cl.on_chat_start
async def main():
    user_name = cl.user_session.get("user").identifier

    user = await User.find_one(User.username == user_name, fetch_links=True)

    active_product = None
    if user:
        await cl.send_window_message({"method": "logged_in"})
        # First try to get the active product
        active_product = await Product.find_one(
            Product.user.id == user.id, Product.active == True
        )

        # Fallback to most recently created product
        if not active_product:
            active_product = await Product.find(
                Product.user.id == user.id
            ).sort([("_id", SortDirection.DESCENDING)]).first_or_none()

        asyncio.create_task(update_products_list(user.products))

    if active_product:
        # Update versions list in the UI
        versions = await list_versions(user_name, active_product.product_id)
        active_version = await get_active_version(user_name, active_product.product_id)
        asyncio.create_task(update_versions_list(versions, active_version))

        # Update deployments list in the UI
        asyncio.create_task(update_deployments_list(active_product.id))

        has_storage = await has_cloud_storage(user_name, active_product.product_id)
        product_id = active_product.product_id
        cl.user_session.set("product_id", active_product.product_id)
        # Newly created product don't have product_name until the first spec is generated
        product_name = active_product.name

        if not product_name or product_name == PRODUCT_NAME_PLACEHOLDER:
            await event_bus.subscribe(CoderCompleted, ProductNameAssignmentConsumer(user_name, product_id))
        elif product_name:
            cl.user_session.set("product_name", product_name)


        if has_storage:
            await cl.Message(
                content=f"Welcome back, here is your last project: {product_name}.").send()
            await populate_from_cloud_storage(user_name, product_id)
            return
        else:
            # We are starting a new project
            await cl.Message(content="Let's build you new product. We can build it together one step at a time,"
                                     " or you can give me the full specification, and I will have it built.").send()
            return
    else:
        # When starting a new project for the first time, set the product_id to session_id
        cl.user_session.set("product_id", cl.user_session.get("id"))

    await cl.Message(
        content="Hello, I'm here to assist you with building your website. We can build it together one step at a time,"
                " or you can give me the full specification, and I will have it built.").send()


@cl.on_window_message
async def window_message(message: str | dict):
    method = "user_message"
    if isinstance(message, dict):
        method = message.get("method")

    product_id = cl.user_session.get("product_id")
    user_name = cl.user_session.get("user").identifier

    if method == "to_builder":
        await handle_user_message(user_name, product_id, message.get("body", "INVALID REQEUST, something went wrong"),
                                  coder_completed_callback=coder_completed,
                                  stream_to_user_callback=ask_user_streaming)
    elif method == "to_generator":
        await handle_user_message(user_name, product_id, message.get("body", "INVALID REQEUST, something went wrong"),
                                  coder_completed_callback=coder_completed,
                                  stream_to_user_callback=ask_user_streaming)
    elif method == "load_template":
        await start_product(
            user_name, product_id,
            landing_page_instructions,
            coder_completed,
            ask_user_streaming
        )
        await update_follow_up_questions_list(landing_page_follow_up_questions)
    elif method == "deploy":
        site_name = message.get("body")
        # TODO: This needs to go away
        # TODO: optimize this. Product_id should come with the request from the forntend
        #  (in fact this is a bug that product is stored in session).
        product = await Product.find_one(Product.product_id == product_id)
        message_text = await run_deployment(user_name, product, site_name)

        await asyncio.gather(cl.Message(content=message_text).send(),
                             cl.send_window_message({"method": "deploy_status", "body": message_text}),
                             update_deployments_list(product.id))
    elif method == "create_new_product":
        await create_blank_product_for(user_name, PRODUCT_NAME_PLACEHOLDER, True)
        await cl.send_window_message({"method": "reload_product"})
    elif method == "product_selected":
        await set_product_active(user_name, message.get("body"))
        await cl.send_window_message({"method": "reload_product"})
    elif method == "delete_product":
        await delete_product(user_name, message.get("body"))
        await cl.send_window_message({"method": "reload_product"})
    elif method == "select_version":
        await set_version_active(user_name, product_id, message.get("body"))
        await cl.send_window_message({"method": "reload_product"})
    else:
        # TODO: remove this, it is replaced by the "ask_user" function callback
        await cl.Message(content=message).send()


@cl.on_message
async def respond(message: Message):
    product_id = cl.user_session.get("product_id")
    user_name = cl.user_session.get("user").identifier

    if len(message.elements) > 1:
        await cl.Message(content="Multiple files are not supported. Please upload one file at a time.").send()
        return
    elif len(message.elements) == 1:
        # This happens when we are uploading a file from the chat window
        try:
            blob_image_path = save_image_file_to_private(user_name, product_id, message.elements[0].name,
                                                         message.elements[0].path,
                                                         message.content)
            message.content = f"Here is a newly uploaded file: {blob_image_path} \n {message.content}.\n\nDon't forget to ask if I would like to upload another file."

            await handle_user_message(user_name, product_id, message.content, coder_completed_callback=coder_completed,
                                      stream_to_user_callback=ask_user_streaming)
        except ValueError as e:
            await cl.Message(content=str(e)).send()
        except Exception as e:
            await cl.Message(
                content="Something went wrong while uploading the file. Try again later, or contact support.").send()
    else:
        # TODO: need some error handling here similar to the above or better
        await handle_user_message(user_name, product_id, message.content, coder_completed_callback=coder_completed,
                                  stream_to_user_callback=ask_user_streaming)


@cl.password_auth_callback
async def auth_callback(username: str, password: str):
    user = await User.find_one(User.username == username)

    if verify_password(password, user.password_hash):
        return cl.User(
            identifier=username, metadata={"role": "user", "provider": "credentials"}
        )
    else:
        return None
