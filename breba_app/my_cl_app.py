import asyncio
from typing import AsyncIterator

import chainlit as cl
from beanie import SortDirection, PydanticObjectId
from bson import DBRef
from chainlit import Message

from auth import verify_password
from breba_app.controllers.product_controller import delete_product, rename_product
from breba_app.models.deployment import Deployment
from breba_app.models.product import Product, create_or_update_product_for, create_blank_product_for, set_product_active
from breba_app.models.user import User
from breba_app.orchestrator import init_state, start_product_task
from breba_app.storage import has_cloud_storage, list_versions, get_active_version, set_version_active
from breba_app.template_agent.product_types.landing_page import landing_page_instructions, \
    landing_page_follow_up_questions
from breba_app.ui_bus import send_index_html_to_ui, send_specification_to_ui, send_index_html_chunk_to_ui, \
    update_products_list, update_versions_list, update_follow_up_questions_list
from controllers.deployment_controller import run_deployment
from llm_utils import get_product_name
from orchestrator import to_builder, to_generator
from storage import save_image_file_to_private, read_spec_text, \
    read_index_html, get_public_url

PRODUCT_NAME_PLACEHOLDER = "Unnamed Product"


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
    spec, product = await asyncio.gather(
        read_spec_text(user_name, session_id),
        read_index_html(user_name, session_id),
    )

    await asyncio.gather(
        init_state(session_id, spec, product),
        send_specification_to_ui(spec),
        send_index_html_to_ui(product)
    )



async def builder_completed(payload: str):
    """
    This is called when the builder agent is done with the specification
    It's primary job is to send website specification to whoever need to see it.
    It also updates user_session in case we just created a new product. (This may be bad design)

    :param payload: website specification
    :return: None
    """
    product_id = cl.user_session.get("product_id")
    user_name = cl.user_session.get("user").identifier
    # TODO: this product creating and naming needs to have a declarative method not piggy back off builder completed
    product_name = cl.user_session.get("product_name")
    # The only time product_name is empty is when we are creating a new product
    if not product_name or product_name == PRODUCT_NAME_PLACEHOLDER:
        product_name = await get_product_name(payload)
        product = await create_or_update_product_for(user_name, product_id, product_name)
        cl.user_session.set("product_name", product.name)

    await send_specification_to_ui(payload)


async def process_generator_message(message: str):
    if message == "__completed__":
        await send_index_html_to_ui(message)
    else:
        await send_index_html_chunk_to_ui(message)


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
        # Newly created product don't hav e product_name until the first spec is generated
        product_name = active_product.name
        if product_name:
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
        await to_builder(user_name, product_id, message.get("body", "INVALID REQEUST, something went wrong"),
                         builder_completed,
                         ask_user_streaming, process_generator_message)
    elif method == "to_generator":
        await to_generator(user_name, product_id, message.get("body", "INVALID REQEUST, something went wrong"),
                           builder_completed, process_generator_message, ask_user_streaming)
    elif method == "load_template":
        await start_product_task(
            user_name, product_id,
            landing_page_instructions,
            builder_completed,
            ask_user_streaming, process_generator_message
        )
        await update_follow_up_questions_list(landing_page_follow_up_questions)
    elif method == "deploy":
        site_name = message.get("body")
        # TODO: This needs to go awaay
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
    elif method == "rename_product":
        body = message.get("body", {})
        product_id_to_rename = body.get("productId")
        new_name = body.get("newName")
        await rename_product(user_name, product_id_to_rename, new_name)
        if product_id == product_id_to_rename:
            cl.user_session.set("product_name", new_name)
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
            message.content = f"Here is a newly uploaded file: {blob_image_path} \n {message.content}.\n\nDon't forget to ask if the I would like to upload another file."
            await to_builder(user_name, product_id, message.content, builder_completed, ask_user_streaming,
                             process_generator_message)
        except ValueError as e:
            await cl.Message(content=str(e)).send()
        except Exception as e:
            await cl.Message(
                content="Something went wrong while uploading the file. Try again later, or contact support.").send()
    else:
        # TODO: need some error handling here similar to the above or better
        await to_builder(user_name, product_id, message.content, builder_completed, ask_user_streaming,
                         process_generator_message)


@cl.password_auth_callback
async def auth_callback(username: str, password: str):
    user = await User.find_one(User.username == username)

    if verify_password(password, user.password_hash):
        return cl.User(
            identifier=username, metadata={"role": "user", "provider": "credentials"}
        )
    else:
        return None
