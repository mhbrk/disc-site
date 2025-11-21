import asyncio
import difflib
import logging

import breba_app.storage
from agent_model import TextPart, Message
from breba_app.generator_agent.accumulator import TagAccumulator
from breba_app.generator_agent.agent import agent as generator_agent
from breba_app.storage import save_files
from breba_app.template_agent.agent import TemplateAgent
from breba_app.template_agent.baml_client.types import WebsiteSpecification
from breba_app.ui_bus import update_versions_list
from builder_agent.agent import agent as builder_agent

logger = logging.getLogger(__name__)


def get_generator_response(session_id: str):
    return generator_agent.get_last_html(session_id)


async def init_state(session_id: str, spec: str, html_output: str):
    await builder_agent.set_agent_prompt(session_id, spec)
    generator_agent.set_last_html(session_id, html_output)
    generator_agent.set_spec(session_id, spec)


def get_html_diff(old_html: str, new_html: str):
    diff = difflib.unified_diff(
        old_html.splitlines(),
        new_html.splitlines(),
        fromfile='a',
        tofile='b',
        lineterm=''
    )
    return "\n".join(diff)


async def process_chunk(accumulator: TagAccumulator, chunk: dict, generator_callback):
    logger.info(f"Processing chunk from agent: {chunk}")
    content = chunk.get("content")
    if not content:
        return

    is_task_completed = chunk.get("is_task_complete")

    # This does not handle the case when input is required
    if is_task_completed:
        await generator_callback("__completed__")
    else:
        tag_html = accumulator.append_and_return_html(content)
        if not tag_html:
            # Accumulate more text before publishing chunk.
            return
        logger.info(f"HTML tag exists: {tag_html}")
        await generator_callback(tag_html)


async def generate_full_website(user_name: str, session_id: str, spec: str, generator_callback):
    logger.info("Generating full website")
    accumulator = TagAccumulator()
    async for chunk in generator_agent.stream(spec, user_name, session_id):
        await process_chunk(accumulator, chunk, generator_callback)


async def generator_task(user_name: str, session_id: str, spec: str, generator_callback):
    try:
        if not generator_agent.get_last_html(session_id):
            # This means we are starting a brand new website.
            logger.info("Existing html not found. Generating full website")
            await generate_full_website(user_name, session_id, spec, generator_callback)
        else:
            # Here we are editing an existing website
            async for update in generator_agent.diffing_spec_update(spec, user_name, session_id):
                update = update.get("content")
                await generator_callback(update)
            await generator_callback("__completed__")
    except Exception as e:
        logger.info(f"Diffing spec update failed: {e}")
        logger.info("Falling back to rebuilding the website from scratch")
        await generate_full_website(user_name, session_id, spec, generator_callback)


async def start_editing_task(user_name: str, session_id: str, query: str, generator_callback):
    try:
        update = await generator_agent.diffing_update(user_name, session_id, query)
        # TODO: this is funky. Using generator_callback like this. Need to use a specialized declarative generator_completed event
        await generator_callback(update)
        await generator_callback("__completed__")
    except Exception as e:
        logger.error(f"Error performing a diffing update: {e}")
        accumulator = TagAccumulator()
        async for chunk in generator_agent.editing_stream(query, user_name, session_id):
            await process_chunk(accumulator, chunk, generator_callback)


async def builder_editing_task(user_name: str, session_id: str, message: str):
    agent_message = Message(role="user", parts=[TextPart(text=message)])
    try:
        agent_response = await builder_agent.edit_invoke(user_name, session_id, agent_message)
    except Exception as e:
        logger.error(f"Error editing spec: {e}")
        logger.info("Falling back to rebuilding the spec")
        agent_response = await builder_agent.invoke(user_name, session_id, agent_message)

    return agent_response


async def to_generator(user_name: str, session_id: str, message: str, builder_completed_callback, generator_callback,
                       message_to_user_callback):
    old_html = generator_agent.get_last_html(session_id)
    await message_to_user_callback("Generator is processing your request...")
    await start_editing_task(user_name, session_id, message, generator_callback)
    new_html = generator_agent.get_last_html(session_id)
    # TODO: use diff module
    diff = get_html_diff(old_html, new_html)

    message_with_instructions = (f"{message} \n"
                                 f"\n In response to the user message, the generator modified the output according to this diff {diff}.\n"
                                 f"When a user requests a change to the website, update the website specification to reflect the new requirement, unless the requested change is already explicitly included in the current specification. Only refrain from updating the specification if the issue was due to an implementation error (i.e., the generator did not follow the existing specification)."
                                 f"IMPORTANT: If the diff shows that an the issue stemmed from a bug in the implementation, do not modify the website specification.")

    # TODO: should probably ask user to confirm
    await message_to_user_callback(
        "Rebuilding the specification... Please wait for completion before doing anything else")
    agent_response = await builder_editing_task(user_name, session_id, message_with_instructions)
    await message_to_user_callback("Rebuild specification task is now complete.")

    new_spec = agent_response.get("content")
    is_task_completed = agent_response.get("is_task_complete")

    if is_task_completed:
        # TODO: This shouldn't be needed. Future calls to generator need to include the actual spec
        generator_agent.set_spec(session_id, new_spec)
        await builder_completed_callback(new_spec)
    else:
        logger.info(f"Waiting for user input: {new_spec}")
        await message_to_user_callback(new_spec)

    new_version = await save_files(user_name, session_id, [("spec.txt", new_spec.encode("utf-8"), "text/plain"),
                                                           ("index.html", new_html.encode("utf-8"), "text/html")])

    versions = await breba_app.storage.list_versions(user_name, session_id)
    await update_versions_list(versions, new_version)


async def to_builder(user_name: str, session_id: str, message: str, builder_completed_callback,
                     message_to_user_callback,
                     generator_callback):
    existing_spec = await builder_agent.get_last_spec(session_id)
    if existing_spec:
        await message_to_user_callback("Builder is working on the specification...")
        agent_response = await builder_editing_task(user_name, session_id, message)

        is_task_completed = agent_response.get("is_task_complete")

        if is_task_completed:
            new_spec = agent_response.get("content")
            await builder_completed_callback(new_spec)
            await message_to_user_callback(
                "Generating preview for the new spec... Use the 📄 from the sidebar to check the new spec")
            await generator_task(user_name, session_id, new_spec, generator_callback)
            new_html = generator_agent.get_last_html(session_id)

            new_version = await save_files(user_name, session_id, [("spec.txt", new_spec.encode("utf-8"), "text/plain"),
                                                                   ("index.html", new_html.encode("utf-8"),
                                                                    "text/html")])
            versions = await breba_app.storage.list_versions(user_name, session_id)
            await update_versions_list(versions, new_version)
        else:
            message = agent_response.get("content")
            logger.info(f"Waiting for user input: {message}")
            await message_to_user_callback(message)
    else:
        await start_product(user_name, session_id, message, builder_completed_callback, message_to_user_callback,
                            generator_callback)


async def start_product(user_name: str, product_id: str, message: str,
                        builder_completed_callback, message_to_user_callback, generator_callback):
    t_agent = TemplateAgent(user_name, product_id)
    response = await t_agent.build_specification(message, message_to_user_callback)

    # We will only proceed to next step, if we have a website specification. Otherwise, wait for additional user input
    if isinstance(response, WebsiteSpecification):
        new_spec = response.spec

        await asyncio.gather(
            builder_agent.set_agent_prompt(product_id, new_spec),
            builder_completed_callback(new_spec),
            message_to_user_callback(
                "Generating preview for the new spec... Use the 📄 from the sidebar to check the new spec"),
            # This is kind of spaghetti code. The coder instructions should probably be on the orchestrator agent state
            generator_task(user_name, product_id, new_spec, generator_callback))

        new_html = generator_agent.get_last_html(product_id)

        new_version = await save_files(user_name, product_id, [("spec.txt", new_spec.encode("utf-8"), "text/plain"),
                                                               ("index.html", new_html.encode("utf-8"), "text/html")])
        versions = await breba_app.storage.list_versions(user_name, product_id)
        await update_versions_list(versions, new_version)
