import chainlit as cl


async def send_specification_to_ui(specification: str):
    await cl.send_window_message({"method": "to_builder", "body": specification})


async def send_index_html_to_ui(html: str):
    await cl.send_window_message({"method": "to_generator", "body": html})
    await cl.send_window_message({"method": "to_generator", "body": "__completed__"})


async def send_index_html_chunk_to_ui(html: str):
    await cl.send_window_message({"method": "to_generator", "body": html})