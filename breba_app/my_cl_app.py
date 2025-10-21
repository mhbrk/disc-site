import asyncio
import logging
from typing import Optional

import chainlit as cl
from chainlit import Message
from beanie import SortDirection, PydanticObjectId
from beanie.odm.operators.update.general import Set
from bson import DBRef

from auth import verify_password
from breba_app.models.deployment import Deployment
from breba_app.models.product import Product
from breba_app.models.user import User
from deployment_controller import run_deployment
from llm_utils import get_product_name
from orchestrator import (
    get_generator_response,
    to_builder,
    update_builder_spec,
    set_generator_response,
    to_generator,
)
from steps_utils import (
    clear_status_log,
    clear_step,
    handle_status_message,
    make_stepped_generator_callback,
    register_step,
)
from storage import (
    save_file_to_private,
    save_image_file_to_private,
    load_template,
    read_spec_text,
    read_index_html,
    get_public_url,
    save_spec,
)

logger = logging.getLogger(__name__)
PRODUCT_NAME_PLACEHOLDER = "Unnamed Product"

async def notify(*args) -> None:
    """Accepts (sender, message) or (message)."""
    msg = args[-1] if args else ""
    if not msg:
        return
    msg = str(msg)

    # These status updates already surface via Chainlit steps, so skip
    # sending them as separate chat bubbles.
    if await handle_status_message(msg):
        return

    await cl.Message(content=msg).send()

# ----------------------------
# Storage helpers
# ----------------------------
# TODO: move this and others to storage module of some kind
async def has_cloud_storage(user_name: str, session_id: str) -> bool:
    spec = read_spec_text(user_name, session_id)
    return spec is not None


async def populate_from_cloud_storage(user_name: str, session_id: str) -> None:
    spec = read_spec_text(user_name, session_id)
    product = read_index_html(user_name, session_id)
    set_generator_response(session_id, spec, product)

    # Stream the HTML into preview
    await process_generator_message(product)
    # Sync spec + sidebar
    await asyncio.gather(
        update_builder_spec(session_id, spec),
        builder_completed(spec),
    )
    # Let UI attach; then explicitly close any spinner
    await asyncio.sleep(0)
    await process_generator_message("__completed__")


async def create_blank_product_for(user_name: str):
    user_obj = await User.find_one(User.username == user_name)

    # Clear all active products
    await Product.find(Product.user.id == user_obj.id, Product.active == True).update(
        Set({Product.active: False})
    )

    product = Product(user=user_obj, name=PRODUCT_NAME_PLACEHOLDER, active=True)
    await product.insert()
    return product

async def set_product_active(user_name: str, product_id: str) -> None:
    user_obj = await User.find_one(User.username == user_name)

    # Clear all active products
    await Product.find(Product.user.id == user_obj.id, Product.active == True).update(
        Set({Product.active: False})
    )

    product = await Product.find_one(Product.product_id == product_id)
    await product.update(Set({Product.active: True}))


async def create_or_update_product_for(user_name: str, product_id: str | None = None, product_spec: str = "",
                                       product_name: str | None = None):
    user_obj = await User.find_one(User.username == user_name, fetch_links=False)

    # Clear all active products
    await Product.find(Product.user.id == user_obj.id, Product.active == True).update(
        Set({Product.active: False})
    )

    # Insert new active product
    product = Product(product_id=product_id, user=user_obj, name=product_name, active=True)
    await Product.find_one(Product.product_id == product_id).upsert(
        Set({
            Product.name: product_name,
            Product.active: True
        }),
        on_insert=product
    )
    return product

# ----------------------------
# Builder / Generator callbacks
# ----------------------------

async def builder_completed(payload: str) -> None:
    product_id = cl.user_session.get("product_id")
    user_name = cl.user_session.get("user").identifier
    product_name = cl.user_session.get("product_name")
    # The only time product_name is empty is when we are creating a new product
    if not product_name or product_name == PRODUCT_NAME_PLACEHOLDER:
        product_name = await get_product_name(payload)
        product = await create_or_update_product_for(user_name, product_id, payload, product_name)
        cl.user_session.set("product_name", product.name)

    save_spec(user_name, product_id, payload)
    builder_message = {"method": "to_builder", "body": payload}
    await cl.send_window_message(builder_message)

async def generator_completed() -> None:
    product_id = cl.user_session.get("product_id")
    user_name = cl.user_session.get("user").identifier

    html = get_generator_response(product_id)

    save_file_to_private(user_name, product_id, "index.html", html, "text/html")

    await cl.Message(
        content="The website is ready to be deployed. Use the 🚀 from the sidebar to deploy your website").send()

async def process_generator_message(message: str) -> None:
    if message == "__start__":
        await set_generator_overlay(True)
    if message == "__completed__":
        await set_generator_overlay(False)
        # Default path uses generator_completed to post final message.
        await generator_completed()
    generator_message = {"method": "to_generator", "body": message}
    await cl.send_window_message(generator_message)


async def set_generator_overlay(visible: bool) -> None:
    command = "show" if visible else "hide"
    await cl.send_window_message({"method": "generator_overlay", "body": command})


# ----------------------------
# Lists for sidebar
# ----------------------------

async def update_deployments_list(product_id: PydanticObjectId) -> None:
    deployments = await Deployment.find(Deployment.product == DBRef("products", product_id)).sort(
        [("deployed_at", SortDirection.DESCENDING)]
    ).to_list()
    if not deployments:
        return
    deployments_list = [
        {"id": str(dep.id), "deployment_id": dep.deployment_id, "url": get_public_url(dep.deployment_id)}
        for dep in deployments
    ]
    await cl.send_window_message({"method": "update_deployments_list", "body": deployments_list})

async def update_products_list(products: list[Product]) -> None:
    products_list = [{"product_id": p.product_id, "name": p.name, "active": p.active} for p in products]
    await cl.send_window_message({"method": "update_products_list", "body": products_list})

# ----------------------------
# Chat lifecycle
# ----------------------------

@cl.on_chat_start
async def main() -> None:
    user_name = cl.user_session.get("user").identifier
    user = await User.find_one(User.username == user_name, fetch_links=True)

    active_product = None
    if user:
        await cl.send_window_message({"method": "logged_in"})
        active_product = await Product.find_one(
            Product.user.id == user.id, Product.active == True
        ) or await Product.find(Product.user.id == user.id).sort(
            [("_id", SortDirection.DESCENDING)]
        ).first_or_none()
        asyncio.create_task(update_products_list(user.products))

    if active_product:
        asyncio.create_task(update_deployments_list(active_product.id))
        has_storage = await has_cloud_storage(user_name, active_product.product_id)
        product_id = active_product.product_id
        cl.user_session.set("product_id", product_id)

        product_name = active_product.name
        if product_name:
            cl.user_session.set("product_name", product_name)

        if has_storage:
            await cl.Message(content=f"Welcome back, here is your last project: {product_name}.").send()
            await populate_from_cloud_storage(user_name, product_id)
            return
        else:
            await cl.Message(
                content="Let's build your new product. We can build it step by step, "
                        "or you can provide a full specification and I will build it."
            ).send()
            return

    cl.user_session.set("product_id", cl.user_session.get("id"))
    await cl.Message(
        content="Hello. We can build your website step by step, or you can provide a full specification."
    ).send()

@cl.on_window_message
async def window_message(message: str | dict) -> None:
    method = "user_message"
    if isinstance(message, dict):
        method = message.get("method")

    product_id = cl.user_session.get("product_id")
    user_name = cl.user_session.get("user").identifier

    if method == "to_builder":
        # Parent step + inner step for generator stream
        inner_cb = make_stepped_generator_callback(
            "Generating preview for the new spec... Use the 📄 from the sidebar to check the new spec",
            process_generator_message,
        )
        await set_generator_overlay(True)
        clear_status_log("builder_step")
        async with cl.Step(name="Builder is working on the specification...") as builder_step:
            register_step("builder_step", builder_step)
            try:
                builder_done = await to_builder(
                    user_name,
                    product_id,
                    message.get("body", "INVALID REQUEST"),
                    builder_completed,
                    inner_cb,       # wrapped generator callback
                    notify,         # same signature as before
                )
            finally:
                clear_step("builder_step")
                await set_generator_overlay(False)
        if builder_done:
            await generator_completed()

    elif method == "to_generator":
        # Optional: small step for the generator-only start (non-nested)
        await set_generator_overlay(True)
        clear_status_log("generator_step")
        async with cl.Step(name="Generator is processing your request...") as generator_step:
            register_step("generator_step", generator_step)
            try:
                generator_done = await to_generator(
                    user_name,
                    product_id,
                    message.get("body", "INVALID REQUEST"),
                    builder_completed,
                    process_generator_message,
                    notify,
                )
            finally:
                clear_step("generator_step")
                await set_generator_overlay(False)
        if generator_done:
            logger.info("Generator flow complete; posting final message")
            await generator_completed()

    elif method == "load_template":
        load_template(user_name, product_id, message.get("body"))
        await populate_from_cloud_storage(user_name, product_id)

    elif method == "deploy":
        site_name = message.get("body")
        product = await Product.find_one(Product.product_id == product_id)
        message_text = await run_deployment(user_name, product, site_name)
        await asyncio.gather(
            cl.Message(content=message_text).send(),
            cl.send_window_message({"method": "deploy_status", "body": message_text}),
            update_deployments_list(product.id),
        )

    elif method == "create_new_product":
        await create_blank_product_for(user_name)
        await cl.send_window_message({"method": "reload_product"})

    elif method == "product_selected":
        await set_product_active(user_name, message.get("body"))
        await cl.send_window_message({"method": "reload_product"})

    else:
        await cl.Message(content=str(message)).send()

@cl.on_message
async def respond(message: Message) -> None:
    product_id = cl.user_session.get("product_id")
    user_name = cl.user_session.get("user").identifier

    if len(message.elements) > 1:
        await cl.Message(content="Multiple files are not supported. Please upload one file at a time.").send()
        return

    if len(message.elements) == 1:
        try:
            blob_image_path = save_image_file_to_private(
                user_name,
                product_id,
                message.elements[0].name,
                message.elements[0].path,
                message.content,
            )
            message.content = (
                f"Here is a newly uploaded file: {blob_image_path}\n{message.content}\n\n"
                "Don't forget to ask if I would like to upload another file."
            )
            inner_cb = make_stepped_generator_callback(
                "Generating preview for the new spec... Use the 📄 from the sidebar to check the new spec",
                process_generator_message,
            )
            await set_generator_overlay(True)
            clear_status_log("builder_step")
            async with cl.Step(name="Builder is working on the specification...") as builder_step:
                register_step("builder_step", builder_step)
                try:
                    await to_builder(
                        user_name,
                        product_id,
                        message.content,
                        builder_completed,
                        inner_cb,
                        notify,
                    )
                finally:
                    clear_step("builder_step")
                    await set_generator_overlay(False)
        except ValueError as e:
            await cl.Message(content=str(e)).send()
        except Exception:
            await cl.Message(
                content="Something went wrong while uploading the file. Try again later, or contact support."
            ).send()
        return

    # Plain-text path
    inner_cb = make_stepped_generator_callback(
        "Generating preview for the new spec... Use the 📄 from the sidebar to check the new spec",
        process_generator_message,
    )
    await set_generator_overlay(True)
    clear_status_log("builder_step")
    async with cl.Step(name="Builder is working on the specification...") as builder_step:
        register_step("builder_step", builder_step)
        try:
            await to_builder(
                user_name,
                product_id,
                message.content,
                builder_completed,
                inner_cb,
                notify,
            )
        finally:
            clear_step("builder_step")
            await set_generator_overlay(False)

@cl.password_auth_callback
async def auth_callback(username: str, password: str):
    user = await User.find_one(User.username == username)
    if verify_password(password, user.password_hash):
        return cl.User(identifier=username, metadata={"role": "user", "provider": "credentials"})
    return None
